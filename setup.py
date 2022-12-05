#
#	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#	INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#	PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
#	FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#	OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#
# Copyright (c) 2020, 2021 Skylark Wireless.
from __future__ import absolute_import
import setuptools
import os

from version import pyfaros_version

# fixme: this excludes SoapySDR
with open('requirements.txt') as fp:
    install_requires = fp.read()

setuptools.setup(
    name="pyfaros",
    version=pyfaros_version,
    author="Skylark Wireless",
    author_email="engineers@skylarkwireless.com",
    test_suite="test",
    description="discover/update skylark wireless devices",
    url="https://github.com/skylarkwireless/pyfaros.git",
    packages=[os.path.join("pyfaros", pkg) for pkg in setuptools.find_packages("pyfaros" )] + ['pyfaros', ],
    package_data={"pyfaros": ["enable_sudo.sh", ]},
    setup_requires=['setuptools_scm'],
    include_package_data=True,
    data_files=[('.',['version.py', 'requirements.txt']),],
    install_requires=install_requires,
    python_requires='>=3.10',
)
