import os
import datetime
import numbers
import asyncio
import tarfile
import pyfaros.discover.discover as discover
import json
import typing
import logging

DEFAULT_SPACING = 4

def get_str_from_indent(indent):
    if isinstance(indent, numbers.Integral):
        return " "*indent
    elif indent is None:
        return ""
    else:
        return indent

def increment_indent(indent, delta=DEFAULT_SPACING):
    if isinstance(indent, numbers.Integral):
        return indent+4
    else:
        return indent

def dump_json_status(device : discover.Remote, fptr : typing.TextIO, indent = None):
    write_header(fptr, "JSON status", indent)
    str_indent = get_str_from_indent(indent)
    for line in json.dumps(device._json, indent=DEFAULT_SPACING).split("\n"):
        print("{}{}".format(str_indent, line), file=fptr)
    print("", file=fptr)

def write_header(fptr : typing.TextIO, header : str, indent = None):
    str_indent = get_str_from_indent(indent)
    pad = 72 - len(str_indent)
    print("{}{}".format(str_indent,   "="*pad), file=fptr)
    print("{}{} {}".format(str_indent, "="*4, header), file=fptr)
    print("{}{}".format(str_indent,   "="*pad), file=fptr)

def write_device_tree(output_dir, device_tree, indent=None):
    filename = os.path.join(output_dir, "device_tree.txt")
    with open(filename, "w") as fptr:
        write_header(fptr, "Device Tree", indent)
        str_indent = get_str_from_indent(indent)
        for line in str(device_tree).split("\n"):
            print("{}{}".format(str_indent, line), file=fptr)
        print("", file=fptr)

async def do_execute_command(device : discover.Remote, fptr : typing.TextIO, header, cmd, indent=None):
    write_header(fptr, header, indent)
    results = await device.ssh_connection.run(cmd, check=True, term_type='xterm')
    if results.exit_status != 0:
        print("Error running command: {}".format(results.command))

    str_indent = get_str_from_indent(indent)
    for line in results.stdout.split("\n"):
        print("{}{}".format(str_indent, line), file=fptr)

async def do_generic_report(device : discover.Remote, filename : str, indent=None):
    with open(filename, "w") as fptr:
        dump_json_status(device, fptr)

async def do_hub_report(device : discover.Remote, filename : str, indent=None):
    cmds = {
        "HUB power status": "sudo hub_cpld -P",
        "HUB power monitor": "sudo hub_cpld -l",
        "HUB fpga info": "sudo hub_fpga -i",
        "HUB clock": "sudo journalctl -n 100 -u hub_clock --no-pager",
        "HUB web monitor": "sudo journalctl -n 100 -u hub_web_monitor --no-pager",
    }

    with open(filename, "w") as fptr:
        dump_json_status(device, fptr)

        for header, cmd in cmds.items():
            await do_execute_command(device, fptr, header, cmd, indent=indent)

        write_header(fptr, "Radio Unit Console output", indent)
        device_indent = increment_indent(indent)
        for chain_idx in range(7):
            for device_idx in range(8):
                # This is stupid simple way to only report the reference node
                #if chain_idx == 6 and device_idx > 0:
                #    continue

                header = "Chain {} Device {}".format(chain_idx+1, device_idx+1)
                cmd = "sudo journalctl --no-pager -n 100 -u sklk-cattty@devices-virtual-tty-ch{}_tty{}".format(chain_idx, device_idx+1)
                await do_execute_command(device, fptr, header, cmd, indent=device_indent)

async def async_do_report_for_a_device(device : discover.Remote, output_dir : str):
    if hasattr(device, "ssh_connect"):
        async with discover.Remote.sshify([device, ]):
            filename = "{}/{}.txt".format(output_dir, device.serial)
            if isinstance(device, discover.HubRemote):
                await do_hub_report(device, filename, indent=0)
            else:
                await do_generic_report(device, filename, indent=0)

async def async_do_report(output_dir, devices : [discover.Remote] or None, recursive=False):
    os.mkdir(output_dir)
    if isinstance(devices, discover.Discover):
        all_devices = list(iter(devices))
    else:
        all_devices = []
        for device in devices:
            for subdevice in device.walk(depth=None if recursive else 0):
                if subdevice not in all_devices:
                    all_devices.append(subdevice)

    return_values = await asyncio.gather(
        *[
            async_do_report_for_a_device(device, output_dir)
            for device in all_devices
        ],
        return_exceptions=True)

    exceptions = [e for e in return_values if isinstance(e, Exception)]
    if exceptions:
        logging.error(exceptions)

def zip_report(dirname : str):
    filename = "{}.tar.gz".format(dirname)
    basename = os.path.basename(dirname)
    with tarfile.open(filename, "w:gz") as fptr:
        fptr.add(dirname, basename, recursive=True)
    return filename

def do_report(top : discover.Discover, devices : [discover.Remote] or None, recursive : bool=False):
    output_dir = "/tmp/sklk_report-{}".format(datetime.datetime.now().strftime("%Y_%m_%dT%H_%M_%S"))
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        async_do_report(
            output_dir, devices if devices is not None else top, recursive=recursive))
    loop.close()
    write_device_tree(output_dir, top)
    filename = zip_report(output_dir)
    print ("Report written to {}".format(filename))
