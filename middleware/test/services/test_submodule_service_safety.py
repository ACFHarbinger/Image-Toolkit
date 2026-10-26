from __future__ import annotations

import os
import subprocess
import sys

import numpy as np
from middleware.src.services.csg.service import _luminance, _save_png
from PIL import Image


def test_service_imports_do_not_require_image_dependencies():
    code = '''
import importlib.abc
import sys
class BlockImages(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"numpy", "cv2", "PIL"}:
            raise ImportError("blocked image dependency: " + fullname)
sys.meta_path.insert(0, BlockImages())
from middleware.src.services.asp.service import StitchService
from middleware.src.services.csg.service import CsgService
StitchService()
CsgService()
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONPATH": "."})
    assert result.returncode == 0, result.stderr


def test_luminance_does_not_overflow():
    rgb = np.array([[[255, 255, 255], [255, 0, 0], [0, 255, 0]]], dtype=np.uint8)
    assert _luminance(rgb).tolist() == [[255, 76, 149]]


def test_save_preserves_existing_partial_and_symlink_target(tmp_path):
    target = tmp_path / "caller.bin"
    target.write_bytes(b"keep caller data")
    output = tmp_path / "out.png"
    partial = tmp_path / "out.png.partial"
    partial.symlink_to(target)
    _save_png(output, np.full((2, 2, 3), 255, dtype=np.uint8))
    assert target.read_bytes() == b"keep caller data"
    assert partial.is_symlink()
    with Image.open(output) as image:
        assert image.size == (2, 2)
    assert not list(tmp_path.glob(".out.png.*.partial"))
