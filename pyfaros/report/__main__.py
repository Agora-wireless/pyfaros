#!/usr/bin/env python3
#
#	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#	INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#	PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
#	FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#	OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#
# Copyright (c) 2020, 2021 Skylark Wireless.

import argparse
import inspect
import sys
import logging
import pkg_resources
import datetime
from pyfaros.discover.discover import Discover
from pyfaros.report.report import do_report

__discover_description = """\
Create a report for devices on the Skylark Wireless network

"""

parser = argparse.ArgumentParser(
    prog="python3 -m pyfaros.report",
    description=__discover_description,
    formatter_class=argparse.RawTextHelpFormatter,
    add_help=False,
)
parser.add_argument(
    'serial', help="Serials to get a detailed report (leave blank for all devices)", nargs="*")

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
do_report(top, devices if parsed.serial else None, recursive=parsed.recursive)

sys.exit(0)
