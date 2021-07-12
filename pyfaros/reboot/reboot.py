#
#	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#	INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#	PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
#	FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#	OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#
# Copyright (c) 2020, 2021 Skylark Wireless.
import asyncio
from pyfaros.discover.discover import Remote

async def async_do_reboot(devices, recursive=False, force=False):
    for device in devices:
        await device.async_do_reboot(recursive=recursive)

def do_reboot(devices, recursive=False, force=False):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_do_reboot(devices, recursive=recursive, force=force))
    loop.close()
