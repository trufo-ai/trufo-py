"""Importing the SDK must not load its optional engines."""

import os
import subprocess
import sys
from pathlib import Path


def test_base_sdk_does_not_import_engine():
    code = """
import importlib.abc
import sys
class BlockEngine(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'tfprov', 'cv2', 'numpy'}:
            raise AssertionError(f'Base SDK imported optional dependency: {fullname}')
sys.meta_path.insert(0, BlockEngine())
import trufo
from trufo.c2pa import ManifestSettings, DigitalSourceType, WatermarkSettings
assert trufo.__version__
assert callable(trufo.sign_c2pa_cloud)
assert ManifestSettings().thumbnail_settings is None
assert WatermarkSettings('fast').profile.value == 'fast'
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    subprocess.run([sys.executable, "-c", code], env=env, check=True)


def test_every_module_imports_without_optional_engines():
    code = """
import importlib
import importlib.abc
import pkgutil
import sys
class BlockOptionalEngines(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'tfprov', 'pawprint'}:
            # raise ModuleNotFoundError, not AssertionError as in the base SDK test, so guarded
            # optional imports take their not-installed branch
            raise ModuleNotFoundError(f'No module named {fullname!r}', name=fullname)
sys.meta_path.insert(0, BlockOptionalEngines())
import trufo
for module in pkgutil.walk_packages(trufo.__path__, 'trufo.'):
    importlib.import_module(module.name)
loaded = [name for name in sys.modules if name.split('.')[0] in {'tfprov', 'pawprint', 'torch'}]
assert not loaded, f'SDK import loaded an optional engine: {loaded}'
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    subprocess.run([sys.executable, "-c", code], env=env, check=True)
