#!/usr/bin/env python3
# Copyright (c) 2020 Skylark Wireless. All Rights Reserved.

import argparse
import inspect
import sys
import logging
import pkg_resources
import datetime
from pyfaros.discover.discover import Discover
from pyfaros.reboot.reboot import do_reboot

__discover_description = """\
Reboot device on the Skylark Wireless network 

"""

parser = argparse.ArgumentParser(
    prog="python3 -m pyfaros.reboot",
    description=__discover_description,
    formatter_class=argparse.RawTextHelpFormatter,
    add_help=False,
)
parser.add_argument(
    'serial', help="Serials to reboot", nargs="+")

general_options = parser.add_argument_group("General Options")
general_options.add_argument(
    "-d", "--debug",
    action="store_true",
    default=False,
    help="Display developer debug prints"
)
general_options.add_argument(
    '-U', '--user', help="Username", action="store", required=True)
general_options.add_argument(
    '-P', '--password', help="Password", action="store", required=True)
general_options.add_argument(
    '-R', '--recursive', help="Reboot all connected devices", action="store_true", required=False)
general_options.add_argument(
    '-f', '--force', help="Reboot all chains whether detected or not", action="store_true", required=False)
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
    '--prefer-ipv6',
    action='store_true',
    help='If devices have both IPv4 and IPv6 addresses, use IPv6 rather than IPv4.',
)

parsed = parser.parse_args()

if parsed.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("asyncssh").setLevel(level=logging.WARN)

top = Discover(soapy_enumerate_iterations=1, ipv6=parsed.prefer_ipv6)
for device in top:
    device.set_credentials(parsed.user, parsed.password)

devices = [device for device in top if device.serial in parsed.serial]
do_reboot(devices, recursive=parsed.recursive, force=parsed.force)

sys.exit(0)
