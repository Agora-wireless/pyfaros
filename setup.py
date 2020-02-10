from __future__ import absolute_import
import setuptools
# fixme: this excludes SoapySDR
with open('requirements.txt') as fp:
  install_requires = fp.read()

setuptools.setup(
    name="pyfaros",
    version="0.0.1",
    author="Skylark Wireless",
    description="discover/update skylark wireless devices",
    url="https://gitlab.com/skylark-wireless/software/sklk-utils/",
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    python_requires='>=3.6',
)
