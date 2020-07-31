# Copyright (c) 2020 Skylark Wireless. All Rights Reserved.
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
    url="https://gitlab.com/skylark-wireless/software/sklk-utils/",
    packages=[os.path.join("pyfaros", pkg) for pkg in setuptools.find_packages("pyfaros" )] + ['pyfaros', ],
    package_data={"pyfaros": ["enable_sudo.sh", ]},
    setup_requires=['setuptools_scm'],
    include_package_data=True,
    data_files=[('.',['version.py', 'requirements.txt']),],
    install_requires=install_requires,
    python_requires='>=3.6',
)
