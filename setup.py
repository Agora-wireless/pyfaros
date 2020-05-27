from __future__ import absolute_import
import setuptools

from version import pyfaros_version

# fixme: this excludes SoapySDR
with open('requirements.txt') as fp:
  install_requires = fp.read()

setuptools.setup(
    name="pyfaros",
    version=pyfaros_version,
    author="Skylark Wireless",
    description="discover/update skylark wireless devices",
    url="https://gitlab.com/skylark-wireless/software/sklk-utils/",
    packages=setuptools.find_packages(),
    data_files=[('.',['requirements.txt']), ('.',['version.py'])],
    install_requires=install_requires,
    python_requires='>=3.6',
)
