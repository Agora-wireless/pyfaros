#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argparse
import asyncio
import logging
import pprint
import sys
import time
from functools import reduce

import SoapySDR
import asyncssh
from typing import Iterable

from pyfaros.discover.discover import Discover, Remote, IrisRemote, HubRemote
from pyfaros.updater.update_environment import UpdateEnvironment

log = logging.getLogger(__name__)


class UpdateError(Exception):
    pass


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
        # await device.ssh_connection.run("sudo -n /sbin/fsck -a -w /dev/mmcblk0p1", term_type='xterm', check=True)
        await device.ssh_connection.run(
            "sudo -n /bin/mount /boot -o rw", term_type='xterm', check=True)
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
        # await device.ssh_connection.run("sudo -n /sbin/fsck -a -w /dev/mmcblk0p1", check=True, term_type='xterm')
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
        cmap_list = lambda d: [
            context.mapping[d.variant].bootbin,
            context.mapping[d.variant].imageub
        ] if (isinstance(d, IrisRemote) or isinstance(
            d, HubRemote)) else [
            context.mapping[d.variant].bootbit,
            context.mapping[d.variant].imageub
        ]

        copy_exceptions = await asyncio.gather(
            *[
                transfer_files(d, cmap_list(d), this_update_timestamp)
                for d in devices
            ],
            return_exceptions=True)

        copy_exceptions = [e for e in copy_exceptions if isinstance(e, Exception)]
        logging.debug(copy_exceptions)

        if len(copy_exceptions) > 0:
            raise UpdateError(copy_exceptions)

        mount_exceptions = await asyncio.gather(
            *[mount_boot(d) for d in devices], return_exceptions=True)

        mount_exceptions = [e for e in mount_exceptions if isinstance(e, Exception)]
        logging.debug(mount_exceptions)

        if len(mount_exceptions) > 0:
            raise UpdateError(mount_exceptions)

        replace_exceptions = await asyncio.gather(
            *[
                replace_files(d, cmap_list(d), this_update_timestamp)
                for d in devices
            ],
            return_exceptions=True)
        
        replace_exceptions = [e for e in replace_exceptions if isinstance(e, Exception)]
        logging.debug(replace_exceptions)

        if len(replace_exceptions) > 0:
            raise UpdateError(replace_exceptions)

        for device in devices:
            await do_reboot(device)


async def find_devices(devices: Iterable[Remote]) -> bool:
    found_devices = await asyncio.get_event_loop().run_in_executor(None, SoapySDR.Device.enumerate)

    def find(device: Remote):
        for found_dict in found_devices:
            if 'serial' in found_dict and found_dict['serial'] == device.serial:
                log.info('Found device {}'.format(device.serial))
                return True
        return False

    return all(find(device) for device in devices)


async def wait_for_devices(devices: Iterable[Remote], interval: int, timeout: int) -> bool:
    start = time.time()

    while time.time() - start <= timeout:
        if await find_devices(devices):
            log.info('Found all devices after the update!')
            return True

        # Only cause for concern if it starts taking more than a minute
        if time.time() - start >= 60:
            log.info('Unable to find all devices, retrying after {} seconds...'.format(interval))

        await asyncio.sleep(interval)

    return False


async def do_update_and_wait(context: UpdateEnvironment, devices: Iterable[Remote],
                             interval: int, timeout: int) -> bool:
    """
    Returns True if the devices are found within `timeout` seconds after the update, False otherwise.
    Devices are polled at an interval of `interval` seconds.
    """
    await do_update(context, devices)

    await asyncio.sleep(interval)
    log.info('Devices updated. Waiting for them to reappear on the network...')

    return await wait_for_devices(devices, interval, timeout)
