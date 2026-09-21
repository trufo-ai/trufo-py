"""Importing the base SDK must not load its optional provenance engine."""

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
from trufo.c2pa import ManifestSettings, DigitalSourceType
assert trufo.__version__
assert callable(trufo.sign_c2pa)
assert ManifestSettings().thumbnail_settings is None
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[2] / "src"))
    subprocess.run([sys.executable, "-c", code], env=env, check=True)
