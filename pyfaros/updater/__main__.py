#!/usr/bin/env python3

import sys
import argparse
import asyncio
import logging
from pyfaros.updater.updater import do_update
from pyfaros.updater.update_file import UpdateFile
from pyfaros.updater.update_environment import UpdateEnvironment
import pyfaros.discover
from pyfaros.discover.discover import Discover, CPERemote, IrisRemote, HubRemote, VgerRemote

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
            prog="python3 -m pyfaros.updater",
            description="Update Skylark Wireless Devices")
    parser.add_argument(
        '--debug', help="turn on debug messages", action="store_true")
    parser.add_argument(
        '--universal',
        help="Path to universal tarball",
        action="store",
        default=None)
    parser.add_argument(
        '--bootbit-only',
        help="Only update bootbit, no other files",
        action="store_true",
        default=False)
    parser.add_argument(
        '--imageub-only',
        help="Only update imageub, no other files",
        action="store_true",
        default=False)
    parser.add_argument(
        '--bootbin-only',
        help="Only update bootbin, no other files.",
        action="store_true",
        default=False)
    parser.add_argument(
        '--file',
        help="Individual tarballs to apply",
        action="append",
        default=[])
    parser.add_argument(
        '--serial', help="Serials to patch", action="append", default=[])
    parser.add_argument(
        '--standalone',
        help="Update all standalone iris nodes",
        action="store_true",
        default=False)
    parser.add_argument(
        '--dry-run',
        help="Don't actuall do the update.",
        action="store_true",
        default=False)

    for device in [IrisRemote, CPERemote, HubRemote, VgerRemote]:
        for v1 in device.Variant:
            for v2 in device.Variant:
                if v2 is not v1:
                    parser.add_argument(
                        '--treat-{}-as-{}'.format(v1.value, v2.value),
                        help="For {}s, treat devices on {} images as if they're on {} images".format(device.__name__, v1, v2),
                        action="store_true",
                        default=False)

    args = parser.parse_args()

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger("asyncssh").setLevel(level=logging.WARN)
    logging.debug("Entered main")

    if args.universal:
        mode = UpdateEnvironment.Mode.UNIVERSAL_TARBALL
    elif args.file:
        mode = UpdateEnvironment.Mode.INDIVIDUAL_TARBALLS
    else:
        parser.print_help()
        sys.exit(0)

    try:
        with UpdateEnvironment(
            universal_tarball_path=args.universal,
            individual_tarball_paths=args.file,
            bootbin_path=None,
            imageub_path=None,
            bootbin_only=False,
            imageub_only=False,
            mode=mode,
            family=None,
            variant=None,
            iwantabrick=False,
            interactive=False) as update_environment:
            logging.debug("Entered ue")

            logging.debug(args)

            logging.debug("Looking for remaps, and remapping")
            for device in [IrisRemote, CPERemote, HubRemote, VgerRemote]:
                for v1 in device.Variant:
                    for v2 in device.Variant:
                        if v2 is not v1:
                            remap_wanted = eval('args.treat_{}_as_{}'.format(v1.value, v2.value))
                            if remap_wanted:
                                logging.debug("Did remap for {} to {}".format(v1.value, v2.value))
                                update_environment.mapping[v1] = update_environment.mapping[v2]


            discovered = sorted(
                filter(update_environment.availablefilter(),
                       list(Discover())),
                key=Discover.Sortings.POWER_DEPENDENCY)
            logging.debug(discovered)
            if args.serial:
                discovered = list(filter(lambda x: x.serial in args.serial, discovered))
            elif args.standalone:
                discovered = list(
                    filter(
                        lambda x: x.rrh is None,
                        filter(lambda x: isinstance(x, IrisRemote),
                               discovered)))
            logging.debug(discovered)
            logging.info("About to flash devices:")
            for device in discovered:
                logging.info("\t {} - {}\n\t\t{}\n\t\t{}\n\t\t{}".format(
                    device.serial, device.address,
                    update_environment.mapping[device.variant].bootbin,
                    update_environment.mapping[device.variant].bootbit,
                    update_environment.mapping[device.variant].imageub))
            if not args.dry_run:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(do_update(update_environment, discovered))
                loop.close()
    except Exception as e:
        logging.debug(e)
        raise e
