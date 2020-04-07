#!/usr/bin/env python3
import asyncio
import datetime
import logging
import time
import urllib
from collections import OrderedDict
from enum import Enum
from functools import reduce, partial
from types import MethodType

import aiohttp
import asyncssh

import SoapySDR

log = logging.getLogger(__name__)

try:
  from contextlib import AsyncExitStack, asynccontextmanager
except ImportError as e:
  try:
    from async_generator import asynccontextmanager
    from async_exit_stack import AsyncExitStack
  except ImportError as e:
    log.fatal(e)
    log.fatal(
        "This library requires community backports from 3.7 for contextlib: async_generator async_exit_stack"
    )
    raise e


class _RemoteEnum(Enum):

  @staticmethod
  def _generate_next_value_(name):
    return str(hash(name))

  def __repr__(self):
    return self.__qualname__.split('.')[0].replace('Remote', '') + "Variant"


class Remote:
  @classmethod
  def mac_to_uaa_id(cls, mac):
    uaa_id = 0
    for byte_idx in range(3):
      uaa_id += ((mac >> (byte_idx*8))&0xff) << ((2-byte_idx)*8)
    return uaa_id

  @asynccontextmanager
  async def _ssh_session_no_connection(self):
    """
        Default method called if a session is to be allocated but no connection
        is currently present, injected into the instance when ssh_connect
        context is held.
        """
    while False:
      yield None
    raise Exception("Connection not currently active?")

  @asynccontextmanager
  async def ssh_connect(self):
    """
        Async context manager handling an ssh connection for a given device.
        Consider using sshify instead.
        """
    async with self._ssh_lock:
      try:
        self.ssh_connection = await asyncssh.connect(
            self.address if "[" not in self.address else self.address[1:-1],
            username="sklk",
            password="sklk",
            known_hosts=None,
            client_keys=[],
        )

        @asynccontextmanager
        async def _ssh_session_has_connection(self):
          yield self.ssh_connection.create_session(
              asyncssh.SSHClientSession, term_type='xterm')
          yield None

        self.ssh_session = MethodType(_ssh_session_has_connection, self)
        yield self.ssh_connection
      finally:
        self.ssh_connection = None
        self.ssh_session = MethodType(Remote._ssh_session_no_connection, self)

  @staticmethod
  @asynccontextmanager
  async def sshify(remotes):
    """
        Async Context Manager where, for each remote in remotes, holding this
        context will transparently hold an ssh context for the remote.
        """
    async with AsyncExitStack() as stack:
      connections = await asyncio.gather(*[
          stack.enter_async_context(remote.ssh_connect()) for remote in remotes
      ])
      yield list(connections)

  def __init__(self, soapy_dict, loop=None):
    self.driver = soapy_dict["driver"] if "driver" in soapy_dict else None
    self.firmware = soapy_dict["firmware"] if "firmware" in soapy_dict else None
    self.fpga = soapy_dict["fpga"] if "fpga" in soapy_dict else None
    self.label = soapy_dict["label"] if "label" in soapy_dict else None
    self.remote_driver = (
        soapy_dict["remote:driver"] if "remote:driver" in soapy_dict else None)
    self.remote = soapy_dict["remote"] if "remote" in soapy_dict else None
    self.remote_type = (
        soapy_dict["remote:type"] if "remote:type" in soapy_dict else None)
    self.revision = soapy_dict["revision"] if "revision" in soapy_dict else None
    self.serial = soapy_dict["serial"] if "serial" in soapy_dict else None
    self.address = None  # default no known url
    self._json_url = None  # default no known url
    self._json = None  # default no json
    self._aioloop = loop if loop is not None else asyncio.get_event_loop()
    # ensure only one connection exists at a time.
    self._ssh_lock = asyncio.Lock(loop=self._aioloop)
    self.ssh_connection = None
    self.ssh_session = MethodType(Remote._ssh_session_no_connection, self)

  @asyncio.coroutine
  async def afetch(self):
    """
        Asynchronous method to fetch additional information from the device.
        """
    if self._json_url is not None:
      log.debug("coro remote called not none")
      async with aiohttp.ClientSession() as session:
        async with session.get(self._json_url) as response:
          self._json = await response.json()
          logging.debug("json successfully set for url {}".format(
              self._json_url))
    else:
      log.debug("url was none")
    return self

  def __str__(self):
    return self.serial

  def __repr__(self):
    return Remote.__str__(self)

  def __iter__(self):
    raise NotImplementedError


class CPERemote(Remote):

  class Variant(_RemoteEnum):
    RRH = "cpe_rrh"
    STANDARD = "cpe"

  def __init__(self, soapy_dict, loop=None):
    super().__init__(soapy_dict, loop=loop)
    self.rrh_head = None
    # About us, set by us
    self.last_mac = None
    self.uaa_id = None
    url = urllib.parse.urlparse(self.remote)
    self.address = url.hostname
    if "fe80" in self.address:
      self.address = "[" + self.address + "]"
    self._json_url = url._replace(scheme="http", netloc=self.address).geturl()
    self.variant = (
        CPERemote.Variant.RRH
        if "rrh" in self.fpga else CPERemote.Variant.STANDARD)
    # After e2400b4a9647f633086d1088b61460c03e79f616 is merged into sklk-dev, we can check device type.
    # https://gitlab.com/skylark-wireless/software/sklk-dev/-/merge_requests/94

  def __iter__(self):
    yield self
    return

  @asyncio.coroutine
  async def afetch(self):
    try:
      await super().afetch()
      self.last_mac = int(self._json["extra"]["gateway_addr"], 16)
      self.uaa_id = self.mac_to_uaa_id(self.last_mac)
      self.rrh_head = (
          reduce(
              lambda x, y: x[y] if x is not None and y in x else None,
              ["sfp", "config", "rrh", "serial"],
              self._json,
          ) is not None)
      return self
    except Exception as e:
      log.debug(e)
      return None

  def __str__(self):
      return "{: <10} - {: <29} - FW: {} FPGA: {}".format(self.serial, self.address,
                                                 self.firmware, self.fpga)

class VgerRemote(Remote):

  class Variant(_RemoteEnum):
    VGER = "vger"

  def __init__(self, soapy_dict, loop=None):
    super().__init__(soapy_dict, loop=loop)
    self.rrh_head = None
    # About us, set by us
    self.last_mac = None
    self.uaa_id = None
    url = urllib.parse.urlparse(self.remote)
    self.address = url.hostname
    if "fe80" in self.address:
      self.address = "[" + self.address + "]"
    self._json_url = url._replace(scheme="http", netloc=self.address).geturl()
    self.variant = VgerRemote.Variant.VGER
    # After e2400b4a9647f633086d1088b61460c03e79f616 is merged into sklk-dev, we can check device type.
    # https://gitlab.com/skylark-wireless/software/sklk-dev/-/merge_requests/94

  def __iter__(self):
    yield self
    return

  @asyncio.coroutine
  async def afetch(self):
    try:
      await super().afetch()
      self.last_mac = int(self._json["extra"]["gateway_addr"], 16)
      self.uaa_id = self.mac_to_uaa_id(self.last_mac)
      self.rrh_head = (
          reduce(
              lambda x, y: x[y] if x is not None and y in x else None,
              ["sfp", "config", "rrh", "serial"],
              self._json,
          ) is not None)
      return self
    except Exception as e:
      log.debug(e)
      return None

  def __str__(self):
    return "{: <10} - {: <29} - FPGA: {}".format(self.serial, self.address,
                                                 self.fpga)

class IrisRemote(Remote):

  class Variant(_RemoteEnum):
    RRH = "iris030_rrh"
    UE = "iris030_ue"
    STANDARD = "iris030"

  def __init__(self, soapy_dict, loop=None):
    super().__init__(soapy_dict, loop=loop)
    # Unique soapy keys
    self.sfp_serial = soapy_dict.get("sfpSerial", None)
    self.sfp_version = soapy_dict.get("sfpVersion", None)
    self.fe_serial = soapy_dict.get("feSerial", None)
    self.fe_version = soapy_dict.get("feVersion", None)
    self.frontend = soapy_dict.get("frontend", None)

    # About us, set by us
    self.last_mac = None
    self.uaa_id = None
    url = urllib.parse.urlparse(self.remote)
    self.address = url.hostname
    if "fe80" in self.address:
      self.address = "[" + self.address + "]"
    self._json_url = url._replace(scheme="http", netloc=self.address).geturl()
    self.rrh_head = None
    self.rrh_index = None
    self.rrh = None
    self.variant = (
        IrisRemote.Variant.RRH if "rrh" in self.fpga else IrisRemote.Variant.UE
        if "ue" in self.fpga else IrisRemote.Variant.STANDARD)
    self.chain_index = None
    # About us, set by hub
    self.hub = None
    self.rrh_member = None
    self.chain = None

  def __iter__(self):
    yield self
    return

  @asyncio.coroutine
  async def afetch(self):
    try:
      await super().afetch()
      self.last_mac = int(self._json["extra"]["gateway_addr"], 16)
      self.uaa_id = self.mac_to_uaa_id(self.last_mac)
      self.rrh_index = int(self._json["global"]["message_index"]) - 1
      self.chain_index = int(self._json["global"]["chain_index"])
      if self.rrh_index >= 0:
        # Force the variant if this is in an rrh
        self.variant = IrisRemote.Variant.RRH
      self.rrh_head = (
          reduce(
              lambda x, y: x[y] if x is not None and y in x else None,
              ["sfp", "config", "rrh", "serial"],
              self._json,
          ) is not None)
      return self
    except Exception as e:
      log.debug(e)
      return None

  def _map_to_hub(self, hubs):
    """
        Called in Discover constructor with all discovered hubs, so that a
        bidirectional mapping can occur, hopefully independently and without
        error.
        """
    for hub in hubs:
      if self.last_mac in hub.macmatches:
        if self.hub is not None:
          raise AssertionError("Remapping iris from {} to {}".format(
              self.hub, hub))
        self.hub = hub
    if self.rrh_member is None:
      self.rrh_member = False

  def details(self):
      return "{: <10} - {: <29} - FW: {} FPGA: {}".format(self.serial, self.address,
                                                 self.firmware, self.fpga)

  def __str__(self):
    return "{}:{}".format(self.rrh_index+1 if self.rrh_index >= 0 else "",
                          self.details())


class NotAnRRH(Exception):
  pass


class RRH:

  def __delitem__(self, key):
    raise NotImplementedError

  def __getitem__(self, key):
    try:
      return self.nodes[key]
    except:
      return None

  def __setitem__(self, key, value):
    raise NotImplementedError

  def __init__(self, members, hub):
    heads = list(filter(lambda x: x.rrh_index == 0 or x.rrh_head, members))
    if len(heads) != 1:
      log.debug("error in RRH constructor arguments")
    self.nodes = []
    self.head = heads[0] if heads else None
    self.address = self.head.address if self.head else None
    self.hub = hub
    sfp_info = self.head._json["sfp"]
    if sfp_info == "None":
      sfp_info = {}
    self.config = sfp_info.get("config", {}).get("rrh", None) if self.head else None
    if self.config is None:
      raise NotAnRRH()
    self.nodes = list(sorted(members, key=lambda x: x.rrh_index))
    self.serial = self.config["serial"]
    self.tail = self.nodes[-1]
    self.chain = getattr(
        reduce(
            lambda x, y: y
            if x is not None and x.chain_index == y.chain_index else None,
            self.nodes,
        ),
        "chain_index",
        None,
    )
    assert (
        self.chain is not None
    ), "Disagreement amongst RRH {} about what chain we're on. {}".format(
        self.serial, [x.chain_index for x in self.nodes])
    # Constructs pairs of node serial / config serials, check for equality,
    # then ensure that you have Trues all the way down.
    self.config_correct = reduce(
        lambda x, y: x and y,
        map(
            lambda x: x[0] == x[1],
            zip(map(lambda x: x.serial, self.nodes), self.config["chain"]),
        ),
        True,
    )
    if not self.config_correct:
      log.info("RRH config doesn't match discovered topology")
    for iris in self.nodes:
      # Map the iris back to us.
      iris.rrh_member = True
      iris.rrh = self
      iris.chain = self.chain

  def __iter__(self):
    return iter(list(sorted(self.nodes, key=lambda x: x.rrh_index)))

  def __str__(self):
    return self.serial


class HubRemote(Remote):

  class Variant(_RemoteEnum):
    REVA = "faroshub04"
    REVB = "faroshub04b"

  def __setitem__(self, key, value):
    """
        You can't inject from python into physical reality... yet.
        """
    raise NotImplementedError

  def __delitem__(self, key):
    """
        You can't delete physical reality... and you never will be able to.
        """
    raise NotImplementedError

  def __getitem__(self, key):
    try:
      return self.chains[key]
    except:
      for chain in self.chains:
        if isinstance(chain, RRH):
          if key == chain.serial:
            return chain
      return None

  def __init__(self, soapy_dict, loop=None):
    super().__init__(soapy_dict, loop=loop)
    self.cpld = soapy_dict["cpld"] if "cpld" in soapy_dict else None
    url = urllib.parse.urlparse(self.remote)
    self.address = url.hostname
    # Annoying hack, aiohttp requires braces on URLs, asyncssh requires
    # they not be present, and urllib has no facilities for injecting and
    # removing them.
    if "fe80" in self.address:
      self.address = "[" + self.address + "]"
    self._json_url = url._replace(
        scheme="http", path="/status.json", netloc=self.address).geturl()
    # represents, as a signed integer, the last 6 nibbles of the mac
    # address, grouped as pairs, reversed as pairs.
    # If you don't get it, just don't worry about it.
    # ie: ab:cd:ef -> 0xefcdab
    self.macmatches = []
    # FIXME: we should inject revision into self.fpga instead.
    self.variant = (
        HubRemote.Variant.REVB
        if "B" is self.revision[-1] else HubRemote.Variant.REVA)
    self.chains = OrderedDict()

  def _map_irises(self, irises):
    """
        Given all possible irises, figure out which ones are connected directly
        to this hub.
        """
    self._irises = list(
        filter(lambda x: x.last_mac in self.macmatches and x.rrh_index >= 0,
               irises))
    for chain in sorted(list({x.chain_index for x in self._irises})):
      this_chain = list(
          sorted(
              filter(lambda x: x.chain_index == chain, self._irises),
              key=lambda x: x.rrh_index,
          ))
      try:
        self.chains[chain] = RRH(this_chain, self)
      except NotAnRRH:
        self.chains[chain] = OrderedDict()
        for iris in this_chain:
          self.chains[chain][iris.rrh_index] = iris
          iris.chain = this_chain

  @asyncio.coroutine
  async def afetch(self):
    try:
      await super().afetch()
      # Get last-3's of macaddress
      self.macmatches = [
          int("".join(reversed(k[3::])), 16)
          for k in map(lambda x: x.split(":"), self._json["jtagblob"]
                       ["network"].values())
      ]
      return self
    except Exception as e:
      log.debug(e)
      return None

  def __iter__(self):
    try:
      yield self
      for chain in self.chains.values():
        if isinstance(chain, RRH):
          yield chain
          for v in chain:
            yield v
        else:
          for c in chain.values():
            yield c
    except StopIteration:
      return


class Discover:
  """
    Performs a network scan (by way of SoapySDR.Device.enumerate()) on
    instantiation, queries devices for additional information, and organizes
    results such that one can query for devices on a hub channel, by chain
    order, etc. Warning: in case you missed that, this constructor will block
    on IO.
    """

  def __init__(self, soapy_enumerate_iterations=3, output=None):
    self.time = datetime.datetime.now()
    # Grab an event loop so that we can get all of the json additional
    # information at once.
    self._loop = asyncio.new_event_loop()
    # Avahi broadcasts occasionally don't respond in time. Do it with a
    # long timeout, and do it a lot, to try to get a good picture.
    soapy_enumerations = {}
    for _ in range(0, soapy_enumerate_iterations):
      for found in map(dict,
                       SoapySDR.Device.enumerate(str(dict(timeoutUs=8e5)))):
        if "serial" in found and found["serial"] not in soapy_enumerations:
          soapy_enumerations[found["serial"]] = found
      time.sleep(1)
    self._soapy_enumerate = list(soapy_enumerations.values())

    # Filter for hubs and irises
    # FIXME: Hacks here until all cpes have a sane fpga string.
    self._irises = list(
        map(
            partial(IrisRemote, loop=self._loop),
            filter(
                lambda x: "remote:type" in
                x.keys() and "iris" in x["remote:type"] and "serial" in x.keys() 
                and "CP" not in x["serial"],
                self._soapy_enumerate,
            ),
        ))

    # FIXME: change this when fpga strings are sane
    self._cpes = list(
        map(
            partial(CPERemote, loop=self._loop),
            filter(
                lambda x: "remote:type" in x.keys() and "cpe" in x["remote:type"] and
                 "serial" in x.keys() and "CP" in x["serial"],
                self._soapy_enumerate,
            ),
        ))

    # FIXME: confirm correct strings for this
    self._vgers = list(
        map(
            partial(VgerRemote, loop=self._loop),
            filter(
                lambda x: "remote:type" in x.keys() and "cpe" in x["remote:type"] and
                 "serial" in x.keys() and "VG" in x["serial"],
                self._soapy_enumerate,
            ),
        ))

    self._hubs = list(
        map(
            partial(HubRemote, loop=self._loop),
            filter(
                lambda x: "remote:type" in x.keys() and "faros" in x[
                    "remote:type"],
                self._soapy_enumerate,
            ),
        ))
    # Stage up the fetches
    iris_fetch_tasks = asyncio.gather(
        *map(
            lambda x: asyncio.ensure_future(x.afetch(), loop=self._loop),
            self._irises,
        ),
        loop=self._loop)
    cpe_fetch_tasks = asyncio.gather(
        *map(
            lambda x: asyncio.ensure_future(x.afetch(), loop=self._loop),
            self._cpes,
        ),
        loop=self._loop)
    vger_fetch_tasks = asyncio.gather(
        *map(
            lambda x: asyncio.ensure_future(x.afetch(), loop=self._loop),
            self._vgers,
        ),
        loop=self._loop)
    hub_fetch_tasks = asyncio.gather(
        *map(
            lambda x: asyncio.ensure_future(x.afetch(), loop=self._loop),
            self._hubs,
        ),
        loop=self._loop)
    # Go, go, go!
    fetchall = asyncio.ensure_future(
        asyncio.gather(
            iris_fetch_tasks, hub_fetch_tasks, cpe_fetch_tasks, vger_fetch_tasks,
            loop=self._loop),
        loop=self._loop,
    )
    self._all = self._loop.run_until_complete(fetchall)
    self._loop.close()
    # Doing this bidirectionally so that neither class modifies the other,
    # it can be more efficient than this, but looping over each provides
    # the opportunity to catch inconsistencies and detect strange
    # scenarios.
    for hub in self._hubs:
      hub._map_irises(self._irises)
    for iris in self._irises:
      iris._map_to_hub(self._hubs)
    self._rrhs = list(
        filter(
            Discover.Filters.RRH,
            reduce(
                lambda x, y: x + y,
                [list(hub.chains.values()) for hub in self._hubs],
                [],
            ),
        ))
    self._standalone_irises = list(
        filter(Discover.Filters.IRIS_STANDALONE, self._irises))
    self._partial_chain_irises = list(
        filter(Discover.Filters.IRIS_PARTIALCHAIN, self._irises))
    self._rrh_member_irises = list(
        filter(Discover.Filters.IRIS_RRHMEMBER, self._irises))

    # Display options
    if output:
      self.single_field = output
    else:
      self.single_field = ""
    self.delim = " "

  def get_common(self, irises, field):
    values = set([getattr(iris, field, None) for iris in irises])
    if len(values) == 0:
      return "no device"
    if len(values) == 1:
      if None in values:
        return "unknown"
      return ' '.join(values)
    else:
      return "mismatch"

  def __str__(self):

    def ctr():
      val = [0]

      def inc():
        val[0] += 1
        return val[0]

      return inc

    c = ctr()
    from treelib import Tree
    t = Tree()
    first_node = c()
    t.create_node("Topology at {}".format(self.time), first_node)
    for hub in self._hubs:
      thishubidx = c()
      t.create_node(
          "Hub: {}    {}".format(hub.serial, hub.address),
          thishubidx,
          parent=first_node)
      for (chidx,
           irises) in [(k, hub.chains[k]) for k in sorted(hub.chains.keys())]:
        if isinstance(irises, RRH) and irises.serial:
          thischainidx = c()
          t.create_node(
              "Chain {}  Serial {}  Count {}  FW {} FPGA {} {}".format(
                  chidx+1, irises.serial, len(list(irises)),
                  self.get_common(irises, 'firmware'),
                  self.get_common(irises, 'fpga'),
                  "(FIX SFP CONFIG)" if not irises.config_correct else ""),
              thischainidx,
              parent=thishubidx,
          )
          if self.single_field:
            iris_list = self.delim.join(
                str(getattr(iris, self.single_field)) for iris in irises)
            t.create_node(iris_list, parent=thischainidx)
          else:
            for iris in irises:
              t.create_node("Iris {}".format(iris), c(), parent=thischainidx)
        elif irises is None:
          continue
        elif len(irises) > 0:
          thischainidx = c()
          t.create_node(
              "Chain {}  Count: {} FW {} FPGA {}  (Not RRH)".format(
                  chidx+1, len(irises),
                  self.get_common(irises.values(), 'firmware'),
                  self.get_common(irises.values(), 'fpga')),
              thischainidx,
              parent=thishubidx,
          )
          if self.single_field:
            iris_list = self.delim.join(
                str(getattr(iris, self.single_field))
                for iris in irises.values())
            t.create_node(iris_list, parent=thischainidx)
          else:
            for j in [irises[k] for k in sorted(irises.keys())]:
              t.create_node("Iris {}".format(str(j+1)), c(), parent=thischainidx)

    if self._standalone_irises:
      standalone = c()
      t.create_node(
          "Standalone Count: {}  FW {} FPGA {}".format(
              len(self._standalone_irises),
              self.get_common(self._standalone_irises, 'firmware'),
              self.get_common(self._standalone_irises, 'fpga')),
          standalone,
          parent=first_node)

      if self.single_field:
        iris_list = self.delim.join(
            str(getattr(iris, self.single_field))
            for iris in self._standalone_irises)
        t.create_node(iris_list, parent=standalone)
      else:
        for iris in self._standalone_irises:
          t.create_node(
              "Iris {}".format(iris.details()), c(), parent=standalone)

    if len(self._cpes) > 0:
      pidx = c()
      t.create_node("Standalone CPEs", pidx, parent=first_node)
      for cpe in self._cpes:
        # Keep the extra space here, formats nicely against Iris being 1 char longer
        t.create_node("CPE  {}".format(str(cpe)), c(), parent=pidx)

    if len(self._vgers) > 0:
      pidx = c()
      t.create_node("Standalone VGERs", pidx, parent=first_node)
      for vger in self._vgers:
        t.create_node("VGER {}".format(str(vger)), c(), parent=pidx)

    return str(t)

  def __iter__(self):
    for hub in self._hubs:
      for value in hub:
        yield value
    for iris in self._standalone_irises:
      yield iris
    for cpe in self._cpes:
      yield cpe
    for vger in self._vgers:
      yield vger

  class Sortings:

    @staticmethod
    def POWER_DEPENDENCY(item):
      """
            sort with this as key to get an iterable back where each subsequent
            item is not power-dependent on the prior.
            """
      if isinstance(item, IrisRemote):
        if item.rrh_index is not None:
          return 0 - item.rrh_index
        return 0
      elif isinstance(item, HubRemote):
        return 1
      return 2

  class Filters:
    # Please maintain item1 as a parameter to filters returning filters and
    # item as the pameter to filters returning booleans.  this allows us to
    # filter it out in argparse below in a simple way.
    @staticmethod
    def SAME_CHAIN(item1):

      def filtering(item2):
        if not isinstance(item1, IrisRemote) or not isinstance(
            item2, IrisRemote):
          return False
        return item1.chain is item2.chain

      return filtering

    @staticmethod
    def RELATED_TO(item1):

      def filtering(item2):
        if item2 is item1:
          return True
        if Discover.Filters.SAME_CHAIN(item1)(item2):
          return True
        hub_test = lambda z: lambda x, y: (y.hub is x) if isinstance(
            x, HubRemote) and isinstance(y, z) else False
        # RRH and Hubs are related
        if hub_test(IrisRemote)(item1, item2) or hub_test(IrisRemote)(item2,
                                                                      item1):
          return True
        if hub_test(RRH)(item1, item2) or hub_test(RRH)(item2, item1):
          return True
        return False

      return filtering

    @staticmethod
    def HUB(item):
      return isinstance(item, HubRemote)

    @staticmethod
    def RRH(item):
      return isinstance(item, RRH)

    @staticmethod
    def IRIS(item):
      return isinstance(item, IrisRemote)

    @staticmethod
    def IRIS_STANDALONE(item):
      if not Discover.Filters.IRIS(item):
        return False
      return item.rrh_member is False and item.hub is None

    @staticmethod
    def IRIS_RRHMEMBER(item):
      if not Discover.Filters.IRIS(item):
        return False
      return item.rrh_member is True and item.hub is not None

    @staticmethod
    def IRIS_PARTIALCHAIN(item):
      if not Discover.Filters.IRIS(item):
        return False
      return item.rrh_member is False and item.hub is not None
