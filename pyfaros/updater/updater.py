#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
import asyncio
import logging
import pprint
import sys
import time
from functools import reduce
import asyncssh
from pyfaros.discover.discover import Discover, Remote, IrisRemote, HubRemote
from pyfaros.updater.update_environment import UpdateEnvironment

log = logging.getLogger(__name__)


async def transfer_files(device, file_list, tmpdir):
  mkdir_cmd = "mkdir /tmp/updater_{}".format(tmpdir)
  try:
    await device.ssh_connection.run(mkdir_cmd, check=True, term_type='xterm')
  except Exception as e:
    logging.debug("{} - {} - {}".format(device, mkdir_cmd, e))
    raise e
  for my_file in file_list:
    if my_file is not None:
      try:
        await asyncssh.scp(
            my_file.path,
            (device.ssh_connection, "/tmp/updater_{}/".format(tmpdir)))
      except Exception as e:
        logging.debug("{} - {} - {}".format(device, "scp", e))
        raise e
  for my_file in file_list:
    if my_file is not None:
      try:
        sha_cmd = "sha256sum /tmp/updater_{}/{}".format(tmpdir,
                                                        my_file.local_name)
        res = await device.ssh_connection.run(
            sha_cmd, term_type='xterm', check=True)
      except Exception as e:
        logging.debug("{} - {} - {}".format(device, sha_cmd, e))
        raise e
      if not res.stdout.split()[0] == my_file.sha256sum:
        raise ValueError("Remote checksum didn't match after copy!")
    logging.debug(
        "file ({}):{} is on {} with proper checksum -\n\t\t{} == {}".format(
            my_file.path, my_file.local_name, device.serial,
            res.stdout.split()[0], my_file.sha256sum))
  return True


async def mount_boot(device):
  try:
    current_mounts = await device.ssh_connection.run(
        "cat /proc/mounts", term_type='xterm', check=True)
    if "/boot" in current_mounts.stdout:
      await device.ssh_connection.run(
          "sudo -n /bin/umount /boot", term_type='xterm', check=True)
    #await device.ssh_connection.run("sudo -n /sbin/fsck -a -w /dev/mmcblk0p1", term_type='xterm', check=True)
    await device.ssh_connection.run(
        "sudo -n /bin/mount /boot", term_type='xterm', check=True)
    logging.debug("{} - fsck'd and boot mounted".format(device.serial))
    return True
  except Exception as e:
    logging.debug("{} - {} - {}: Dump".format(device, "checking boot", e))
    raise e


async def replace_files(device, file_list, tmpdir):
  for my_file in file_list:
    logging.debug(my_file)
    copy_command = "sudo -n cp /tmp/updater_{}/{} /boot/{}".format(
        tmpdir, my_file.local_name, my_file.remote_name)
    try:
      await device.ssh_connection.run(
          copy_command, check=True, term_type='xterm')
    except Exception as e:
      logging.debug("FAILED: {} - {}".format(device, copy_command))
      logging.debug(e)
      logging.debug("Copy of {} -> {} failed on remote target {}".format(
          my_file.local_name, my_file.remote_name, device.serial))
      raise e
  try:
    await device.ssh_connection.run(
        "sudo -n /bin/sync", check=True, term_type='xterm')
    await device.ssh_connection.run(
        "sudo -n /bin/umount /boot", check=True, term_type='xterm')
    #await device.ssh_connection.run("sudo -n /sbin/fsck -a -w /dev/mmcblk0p1", check=True, term_type='xterm')
    return True
  except Exception as e:
    logging.debug("{} - {} - {}".format(device, "sudo -n /bin/sync", e))
    raise e


async def do_reboot(device):
  await device.ssh_connection.run(
      "sudo -n systemctl reboot", check=True, term_type='xterm')
  return True


async def do_update(context, devices):
  this_update_timestamp = str(time.time()).split('.')[0]
  async with Remote.sshify(devices):
    try:
      cmap_list = lambda d: [
          context.mapping[d.variant].bootbin, 
          context.mapping[d.variant].imageub
      ] if (isinstance(d, IrisRemote) or isinstance(
          d, HubRemote)) else [
              context.mapping[d.variant].bootbit, 
              context.mapping[d.variant].imageub
          ]

      copy_results = await asyncio.gather(
          *[
              transfer_files(d, cmap_list(d), this_update_timestamp)
              for d in devices
          ],
          return_exceptions=True)
      logging.debug(copy_results)
      if reduce(lambda x, y: x and y, copy_results, True) is not True:
        sys.exit(1)
      mount_exceptions = await asyncio.gather(
          *[mount_boot(d) for d in devices], return_exceptions=True)
      logging.debug(mount_exceptions)
      if reduce(lambda x, y: x and y, copy_results, True) is not True:
        sys.exit(1)
      replace_exceptions = await asyncio.gather(
          *[
              replace_files(d, cmap_list(d), this_update_timestamp)
              for d in devices
          ],
          return_exceptions=True)
      logging.debug(replace_exceptions)
      if reduce(lambda x, y: x and y, copy_results, True) is not True:
        sys.exit(1)
    except Exception as e:
      logging.debug(e)
      sys.exit(1)
    for device in devices:
      await do_reboot(device)

