#!/usr/bin/env python3

import argparse
import inspect
import sys
import logging
import pkg_resources
from pyfaros.discover.discover import Discover

__discover_description = """\
Discover Skylark Wireless network topologies

RRH Chain index starts at 1.
RRH Iris node index starts at 1.
"""

filtermapping = {
    str(f).lower().replace("_", "-"): getattr(Discover.Filters, f)
    for f in dir(Discover.Filters)
    if callable(getattr(Discover.Filters, f)) and not "__" in f and
    "item1" not in str(inspect.signature(getattr(Discover.Filters, f)))
}

parser = argparse.ArgumentParser(
    prog="python3 -m pyfaros.discover",
    description=__discover_description,
    formatter_class=argparse.RawTextHelpFormatter,
    add_help=False,
)

general_options = parser.add_argument_group("General Options")
general_options.add_argument(
    "-s", "--simplified",
    dest="output",
    action="store_const",
    const="serial",
    help="Displays all of the serial numbers for each RRH in one line.",
    default=None,
)
general_options.add_argument(
    "-d", "--debug",
    action="store_true",
    default=False,
    help="Display developer debug prints"
)
general_options.add_argument(
    "-v", "--version",
    action="version",
    #version="pyfaros-{}".format(dir(pyfaros)),
    version="pyfaros-{}".format(pkg_resources.get_distribution("pyfaros").version),
    help="Displays the version and then exits.",
)
general_options.add_argument(
    "-h", "--help",
    action="help",
    default=argparse.SUPPRESS,
    help="Displays this help message and then exits.",
)

advanced_options = parser.add_argument_group("Advanced Options")
advanced_options.add_argument(
    "-o", "--output",
    choices=["serial", "address"],
    help="Display a single field for each node. Uses one line per RRH.",
    default=None,
)
advanced_options.add_argument(
    "--filter",
    choices=filtermapping,
    help="Apply filter before printing the device information.  Only works with --no-tree and does not work with --sort.",
)
advanced_options.add_argument(
    "--sort",
    dest='sort',
    action='store_true',
    help="Apply sorting before printing the device information.  Only works with --no-tree.",
)
advanced_options.add_argument(
    "--no-sort",
    dest='sort',
    action='store_false',
    help="Do not apply sorting before printing the device information.  Only works with --no-tree.",
)
advanced_options.add_argument(
    "--no-tree",
    dest='flat',
    help="Don't display the tree graphics.",
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
