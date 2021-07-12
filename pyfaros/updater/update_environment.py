#
#	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#	INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#	PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
#	FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#	OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#
# Copyright (c) 2020, 2021 Skylark Wireless.
import logging
import pathlib
import shutil
import tempfile
from collections import namedtuple
from enum import Enum, auto
from glob import glob

import typing
from typing import Mapping, List

from pyfaros.discover.discover import (CPERemote, HubRemote, IrisRemote,
                                             Remote, VgerRemote)
from pyfaros.updater.update_file import (BootBin, BootBit, ImageUB, Ps7Init,
                                                 Manifest, TarballFile, UpdateFile)

_getfirst = lambda x: x[0] if len(x) > 0 else None

log = logging.getLogger(__name__)

def _fill_namedtup(mapping, variant, manifest=None, imageub=None, bootbin=None):
    nt = mapping[variant]
    m_file = _getfirst(glob(nt.unpackdir + "/manifest.txt"))
    b_file = _getfirst(glob(nt.unpackdir + "/BOOT.BIN"))
    i_file = _getfirst(glob(nt.unpackdir + "/image.ub"))
    bit_file = _getfirst(glob(nt.unpackdir + "/*_top.bin"))
    ps7_init = _getfirst(glob(nt.unpackdir + "/ps7_init.tcl"))

    if m_file is not None:
        nt.manifest = Manifest(m_file)
    if b_file is not None:
        nt.bootbin = BootBin(b_file, manifest=nt.manifest, variant_given=variant)
    if i_file is not None:
        nt.imageub = ImageUB(i_file, manifest=nt.manifest, variant_given=variant)
    if bit_file is not None:
        nt.bootbit = BootBit(bit_file, manifest=nt.manifest, variant_given=variant)
    if ps7_init is not None:
        nt.ps7_init = Ps7Init(ps7_init, manifest=nt.manifest, variant_given=variant)


class UpdateEnvironment:

    class Mode(Enum):
        FILES_DIRECTLY = auto()
        INDIVIDUAL_TARBALLS = auto()
        UNIVERSAL_TARBALL = auto()

    def __init__(self,
                 universal_tarball_path=None,
                 individual_tarball_paths=[],
                 individual_manifest=None,
                 bootbin_path=None,
                 bootbit_path=None,
                 imageub_path=None,
                 bootbin_only=False,
                 bootbit_only=False,
                 imageub_only=False,
                 mode=None,
                 family=None,
                 variant=None,
                 iwantabrick=None,
                 interactive=False):
        self.bootbin_only = bootbin_only
        self.bootbit_only = bootbit_only
        self.imageub_only = imageub_only
        self.universal_tarball_path = universal_tarball_path
        self.individual_manifest = None
        self.individual_tarball_paths = individual_tarball_paths
        self.bootbin_path = bootbin_path
        self.bootbit_path = bootbit_path
        self.imageub_path = imageub_path
        self.mode = mode
        self.family = family
        self.variant = variant
        self.iwantabrick = iwantabrick
        self.interactive = interactive
        self.devices = None
        self.root_tmpdir = None
        self.mapping = {
            v: namedtuple("UpdateFiles",
                          "manifest imageub bootbin bootbit unpackdir ps7_init")
            for v in list(IrisRemote.Variant) + list(HubRemote.Variant) +
            list(CPERemote.Variant) + list(VgerRemote.Variant)
        }
        if self.mode is None or self.mode not in list(UpdateEnvironment.Mode):
            e = ValueError("Update context mode must be one of {}".format(
                list(UpdateEnvironment.Mode)))
            logging.fatal(e)
            raise e
        if self.mode is UpdateEnvironment.Mode.UNIVERSAL_TARBALL and self.universal_tarball_path is None:
            e = ValueError("Mode is wrong, universal tarball path is None")
            logging.fatal(e)
            raise e
        if self.mode is UpdateEnvironment.Mode.INDIVIDUAL_TARBALLS and len(
            individual_tarball_paths) < 1:
            e = ValueError("Mode is individual tarballs but none given?")
            logging.fatal(e)
            raise e

    def __enter__(self):
        # Folder to temporarily hold unpacked files.
        logging.debug("Entered __enter__ for ue")
        self.root_tmpdir = tempfile.mkdtemp()
        pathlib.Path(self.root_tmpdir + "/.unpack").mkdir(
            parents=False, exist_ok=False)
        for k, v in self.mapping.items():
            v.unpackdir = self.root_tmpdir + "/" + k.value + "/.unpack"
            pathlib.Path(v.unpackdir).mkdir(parents=True, exist_ok=False)
            v.manifest = None
            v.imageub = None
            v.bootbin = None
            v.bootbit = None
            v.ps7_init = None

        logging.debug(self.mode)
        if self.mode == UpdateEnvironment.Mode.UNIVERSAL_TARBALL:
            logging.debug("self.mode was universal tarball")
            shutil.unpack_archive(self.universal_tarball_path,
                                  self.root_tmpdir + "/.unpack")
            outer_manifest = None
            try:
                if len(glob(self.root_tmpdir + "/.unpack/manifest.txt")) == 1:
                    outer_manifest = Manifest(
                        _getfirst(glob(self.root_tmpdir + "/.unpack/manifest.txt")))
            except FileNotFoundError:
                # Some images don't have an outer manifest, is ok.
                outer_manifest = None
                logging.debug("Didn't have outer manifest.")
            logging.debug("about to deal with tarballs")
            for tarball in glob(self.root_tmpdir + "/.unpack/" + "*.tar.gz"):
                logging.debug("dealing with tarball {}".format(tarball))
                as_obj = TarballFile(tarball, manifest=outer_manifest)
                if as_obj.variant_specific_detected is None or as_obj.variant_specific_detected not in self.mapping:
                    logging.debug("Couldn't get variant for tarball {}".format(tarball))
                    raise ValueError(
                        "Couldn't get variant for tarball {}".format(tarball))
                else:
                    as_obj.set_unpackdir(
                        self.mapping[as_obj.variant_specific_detected].unpackdir)
                as_obj.unpack()
                _fill_namedtup(self.mapping, as_obj.variant_specific_detected)

        elif self.mode == UpdateEnvironment.Mode.INDIVIDUAL_TARBALLS:
            outer_manifest = None
            if self.individual_manifest is not None:
                if len(glob(self.root_tmpdir + "/.unpack/manifest.txt")) == 1:
                    outer_manifest = Manifest(
                        _getfirst(glob(self.root_tmpdir + "/.unpack/manifest.txt")))
                    logging.debug(outer_manifest)
            for tarball in self.individual_tarball_paths:
                log.debug(tarball)
                as_obj = TarballFile(
                    tarball,
                    manifest=outer_manifest,
                    family_given=self.family,
                    variant_given=self.variant)
                if (as_obj.variant_specific_detected is None or
                    as_obj.variant_specific_detected not in self.mapping
                   ) and self.variant is None:
                    raise ValueError(
                        "Couldn't get variant for tarball {}".format(tarball))
                else:
                    if self.variant is not None:
                        as_obj.variant_specific_detected = self.variant
                    as_obj.set_unpackdir(
                        self.mapping[as_obj.variant_specific_detected].unpackdir)
                as_obj.unpack()
                _fill_namedtup(self.mapping, as_obj.variant_specific_detected)

        elif self.mode == UpdateEnvironment.Mode.FILES_DIRECTLY:
            if self.variant is not None:
                if self.imageub_path is not None:
                    self.mapping[self.variant].imageub = ImageUB(
                        self.imageub_path, variant_given=self.variant)
                if self.bootbin_path is not None:
                    self.mapping[self.variant].bootbin = BootBin(
                        self.bootbin_path, variant_given=self.variant)
                if self.bootbit_path is not None:
                    self.mapping[self.variant].bootbit = BootBit(
                        self.bootbin_path, variant_given=self.variant)
            else:
                raise ValueError("Must provide variant for standalone image")

        for k, v in self.mapping.items():
            logging.debug("for targets {}:{}".format(k, v))
            logging.debug("\tbootbit: {}".format(v.bootbit))
            logging.debug("\tbootbin: {}".format(v.bootbin))
            logging.debug("\timageub: {}".format(v.imageub))
            logging.debug("\tmanifest: {}".format(v.manifest))

        return self

    def availablefilter(self):

        def filterfunc(item):
            if not isinstance(item, Remote):
                return False
            else:
                if item.variant in self.mapping.keys():
                    if self.bootbin_only and (self.mapping[item.variant].bootbin is None):
                        return False
                    if self.imageub_only and (self.mapping[item.variant].imageub is None):
                        return False
                    if self.mapping[item.variant].bootbin is None and self.mapping[item.variant].bootbit is None and self.mapping[item.variant].imageub is None:
                        return False
                    return True

        return filterfunc

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            shutil.rmtree(self.root_tmpdir, ignore_errors=True)
        except Exception as e:
            raise e
