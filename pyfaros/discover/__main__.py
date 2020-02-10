#!/usr/bin/env python3

import argparse
import inspect
import sys
import logging
from pyfaros.discover.discover import Discover

filtermapping = {
    str(f).lower().replace("_", "-"): getattr(Discover.Filters, f)
    for f in dir(Discover.Filters)
    if callable(getattr(Discover.Filters, f)) and not "__" in f and
    "item1" not in str(inspect.signature(getattr(Discover.Filters, f)))
}

parser = argparse.ArgumentParser(
    prog="python3 -m pyfaros.discover",
    description="discover Skylark Wireless network topologies")
parser.add_argument(
    "--output",
    choices=["serial", "address"],
    help="Type of output to produce",
    default=None,
)
parser.add_argument(
    "--filter",
    choices=filtermapping,
    help="apply filter before printing addresses or serials, ignored if --output is tree (todo: currently)",
)
parser.add_argument("--debug", help="", action="store_true", default=False)
parser.add_argument(
    "--sort",
    dest='sort',
    action='store_true',
    help="apply sorting before printing addresses or serials, ignored if --output is tree (todo: currently)",
)
parser.add_argument(
    "--no-sort",
    dest='sort',
    action='store_false',
)
parser.add_argument(
    "--flat",
    dest='flat',
    action='store_true',
)
parsed = parser.parse_args()

if parsed.debug:
  logging.basicConfig(level=logging.DEBUG)
else:
  logging.basicConfig(level=logging.ERROR)

top = Discover(soapy_enumerate_iterations=1, output=parsed.output)
if parsed.flat:
  iteration = sorted(
      top, key=Discover.Sortings.POWER_DEPENDENCY
  ) if parsed.sort else top if parsed.filter is None else filter(
      filtermapping[parsed.filter], top)
  for i in iteration:
    if parsed.output:
      print(eval("i.{}".format(parsed.output)))
    else:
      print(str(i))
else:
  print(top)
sys.exit(0)
