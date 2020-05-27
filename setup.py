from __future__ import absolute_import
import setuptools
import git

sha = git.Repo(search_parent_directories=True).head.object.hexsha[:8]

# fixme: this excludes SoapySDR
with open('requirements.txt') as fp:
  install_requires = fp.read()

setuptools.setup(
    name="pyfaros",
    version="0.0.4-{}".format(sha),
    author="Skylark Wireless",
    description="discover/update skylark wireless devices",
    url="https://gitlab.com/skylark-wireless/software/sklk-utils/",
    packages=setuptools.find_packages(),
    data_files=[('.',['requirements.txt']), ],
    install_requires=install_requires,
    python_requires='>=3.6',
)
