import hashlib
import logging
import os
import shutil
import subprocess
from functools import partial

from pyfaros.discover.discover import CPERemote, HubRemote, IrisRemote

log = logging.getLogger(__name__)

def sha256sum(filename):
  try:
    with open(filename, mode='rb') as file_handle:
      hashguy = hashlib.sha256()
      for buf in iter(partial(file_handle.read, 128), b''):
        hashguy.update(buf)
    return hashguy.hexdigest()
  except:
    raise


class UpdateFile:

  def __init__(self,
               path,
               manifest=None,
               family_given=None,
               variant_given=None):
    self.path = path
    self.local_name = os.path.basename(self.path)
    self.remote_name = None
    self.sha256sum = sha256sum(path)
    self.manifest = manifest
    self.manifest_match = False
    self.family_given = family_given
    self.variant_given = variant_given
    self.variant_family_detected, self.variant_specific_detected = self._test_for_variant(
    )
    if self.manifest is not None:
      self.manifest_match = manifest.check_file(self)

  def __repr__(self):
    return str(self)

  def __str__(self):
    return "{} -({} from {}) {} - ManifestMatch? {}".format(self.path,
                                                self.remote_name,
                                                self.local_name,
                                                self.sha256sum,
                                                self.manifest_match)

  def variant_specific_check_command(self):
    raise NotImplementedError

  def variant_family_check_command(self):
    raise NotImplementedError

  def _test_for_variant(self):
    if self.family_given is not None and self.variant_given is not None:
      return (self.family_given, self.variant_given)
    v_family = None
    v_specific = None
    if self.variant_family_check_command() is not None:
      run = subprocess.run(
          str(self.variant_family_check_command()).format(self.path),
          shell=True,
          check=True,
          encoding="utf-8",
          stdout=subprocess.PIPE)
      if run.returncode != 0:
        raise ValueError(
            "{0} created for path {1}, but that file does not seem to be a {0} or does not exist"
            .format(self.__class__.__name__, self.path))
      v_family = IrisRemote.Variant if "iris030" in run.stdout else HubRemote.Variant if "faroshub04" in run.stdout else CPERemote.Variant if "cpe" in run.stdout else None
    # Specific
    if v_family is not None and self.variant_specific_check_command(
    ) is not None:
      if self.variant_specific_check_command() is not None:
        run2 = subprocess.run(
            str(self.variant_specific_check_command()).format(self.path),
            shell=True,
            check=True,
            encoding="utf-8",
            stdout=subprocess.PIPE)
        if run2.returncode != 0:
          raise ValueError("command failed? {}".format(str(run2.args)))
        else:
          if v_family is IrisRemote.Variant:
            v_specific = IrisRemote.Variant.UE if "ue" in run2.stdout else IrisRemote.Variant.RRH if "rrh" in run2.stdout else IrisRemote.Variant.STANDARD if "iris030" in run2.stdout else None
          elif v_family is HubRemote.Variant:
            v_specific = HubRemote.Variant.REVB if "faroshub04b" in str(
                run2.stdout
            ) else HubRemote.Variant.REVA if "faroshub04" in run2.stdout else None
          elif v_family is CPERemote.Variant:
            v_specific = CPERemote.Variant.RRH if "cpe_rrh" in str(
                run2.stdout
            ) else CPERemote.Variant.STANDARD if "cpe" in run2.stdout else None
    return (v_family, v_specific)


class ImageUB(UpdateFile):

  def __init__(self, path, manifest=None, variant_given=None):
    super().__init__(path, manifest=manifest, variant_given=variant_given)
    if isinstance(variant_given, CPERemote.Variant):
      self.remote_name = "sklk_cpe_image.ub"
    else:
      self.remote_name = "image.ub"

  def variant_family_check_command(self):
    return "strings {} | grep PetaLinux | cut -d'/' -f3"

  def variant_specific_check_command(self):
    return None

class Ps7Init(UpdateFile):

  def __init__(self, path, manifest=None, variant_given=None):
    super().__init__(path, manifest=None, variant_given=variant_given) # Not in manifest, always set to None
    
    self.remote_name = "ps7_init.tcl" # Should never need to copy this file

  def variant_family_check_command(self):
    return None

  def variant_specific_check_command(self):
    return None

class BootBin(UpdateFile):

  def __init__(self, path, manifest=None, variant_given=None):
    super().__init__(path, manifest=manifest, variant_given=variant_given)
    self.remote_name = "BOOT.BIN"

  def variant_family_check_command(self):
    return "strings {} | grep -i preboot | cut -d' ' -f4- | xargs | cut -d';' -f1"

  def variant_specific_check_command(self):
    return None


class BootBit(UpdateFile):

  def __init__(self, path, manifest=None, variant_given=None):
    super().__init__(path, manifest=manifest, variant_given=variant_given)
    #assert (issubclass(variant_given, CPERemote.Variant)) Sometimes detected.
    self.remote_name = "sklk_cpe_top.bin"

  def variant_family_check_command(self):
    return None

  def variant_specific_check_command(self):
    return None


class TarballFile(UpdateFile):

  def __init__(self,
               path,
               unpackpath=None,
               manifest=None,
               family_given=None,
               variant_given=None):
    super().__init__(
        path,
        manifest=manifest,
        family_given=family_given,
        variant_given=variant_given)
    log.debug("tarballfile made")
    self.unpackpath = unpackpath

  def variant_family_check_command(self):
    return "ls {}"

  def variant_specific_check_command(self):
    return "ls {}"

  def unpack(self):
    if self.unpackpath is None:
      log.debug("failed unpacking {} to {}!".format(self.path,
                                                        self.unpackpath))
      raise ValueError("Can't unpack tarball without path being set")
    else:
      log.debug("unpacking {} to {}!".format(self.path, self.unpackpath))
      shutil.unpack_archive(self.path, self.unpackpath)
      # Attempt to also unpack the nested cpe_auto.hdf TODO maybe this code doesn't belong here
      auto_path_hdf = os.path.join(self.unpackpath, 'cpe_auto.hdf')
      if os.path.isfile(auto_path_hdf):
        logging.debug("Found cpe_auto.hdf")
        shutil.unpack_archive(auto_path_hdf, self.unpackpath, format="zip")

  def set_unpackdir(self, unpackdir):
    if self.unpackpath is not None:
      raise FileExistsError("Setting unpack path twice?")
    self.unpackpath = unpackdir


class Manifest:

  def __init__(self, manifest_filename):
    log.debug("Instantiating manifest with path {}".format(manifest_filename))
    self.manifest_filename = manifest_filename
    self._map = {}
    try:
      with open(self.manifest_filename) as f:
        for cnt, line in enumerate(f):
          sha256, fname = line.split()
          fname = os.path.basename(fname)
          self._map[fname] = sha256
    except FileNotFoundError as fnfe:
      raise fnfe
    log.debug("Instantiated manifest with keys, hashes ({})".format(self._map))

  def __str__(self):
    return self.manifest_filename

  def __repr__(self):
    return self.manifest_filename

  def tracked_files(self):
    """ List files in the manifest """
    return list(self._map.keys())

  def check_file(self, the_file):
    log.debug("Checking manifest at {} against file object {} str({})".format(
        self.manifest_filename, the_file, str(the_file)))
    assert isinstance(
        the_file, UpdateFile), "Checking manifest against non UpdateFile object"
    if not the_file.local_name in self._map:
      error = KeyError("Manifest does not have file {}".format(
          the_file.local_name))
      log.debug(error)
      raise error
    if not self._map[the_file.local_name] == the_file.sha256sum:
      error = ValueError(
          "Manifest sha256sum does not match file sha256sum: \nmanifest.txt({}) != {}({})"
          .format(self._map[the_file.local_name], the_file.local_name,
                  the_file.sha256sum))
      log.debug(error)
      raise error
    return True
