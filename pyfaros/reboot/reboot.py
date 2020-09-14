import asyncio
from pyfaros.discover.discover import Remote

async def async_do_reboot(devices, recursive=False):
    for device in devices:
        await device.async_do_reboot(recursive=recursive)

def do_reboot(devices, recursive=False):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_do_reboot(devices, recursive=recursive))
    loop.close()
