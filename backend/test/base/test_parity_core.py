"""
backend/test/base/test_parity_core.py
======================================
Phase 12 integration tests for base.core (Phase 8 C++ functions).

Tests are skipped when the C++ base extension is not built or when
OpenCV is unavailable. No mocking — these are real function calls.

Run (when base is built):
    pytest backend/test/base/test_parity_core.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest

import numpy as np
import pytest

try:
    import base as _base

    HAS_BASE = hasattr(_base, "core")
except ImportError:
    HAS_BASE = False

try:
    import cv2

    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

pytestmark = pytest.mark.skipif(
    not HAS_BASE or not HAS_CV2,
    reason="base C++ extension not built or cv2 unavailable",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_png(path: str, w: int, h: int, color=(128, 64, 32)) -> None:
    img = np.full((h, w, 3), color, dtype=np.uint8)
    cv2.imwrite(path, img)


def _write_identical_png(path: str, seed_img: np.ndarray) -> None:
    cv2.imwrite(path, seed_img)


# ---------------------------------------------------------------------------
# convert_single_image
# ---------------------------------------------------------------------------

class TestConvertSingleImage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="base_core_cvt_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_png_to_jpeg_output_readable(self):
        src = os.path.join(self.tmpdir, "src.png")
        dst = os.path.join(self.tmpdir, "out.jpg")
        _write_png(src, 100, 100)
        _base.core.convert_single_image(src, dst, 100, 100, "stretch", False)
        assert os.path.exists(dst)
        img = cv2.imread(dst)
        assert img is not None

    def test_aspect_crop_output_is_square(self):
        src = os.path.join(self.tmpdir, "tall.png")
        dst = os.path.join(self.tmpdir, "crop.jpg")
        _write_png(src, 50, 100)
        _base.core.convert_single_image(src, dst, 50, 50, "crop", False)
        img = cv2.imread(dst)
        assert img is not None
        assert img.shape[0] == 50 and img.shape[1] == 50

    def test_aspect_pad_output_has_target_size(self):
        src = os.path.join(self.tmpdir, "wide.png")
        dst = os.path.join(self.tmpdir, "pad.png")
        _write_png(src, 100, 50)
        _base.core.convert_single_image(src, dst, 100, 100, "pad", False)
        img = cv2.imread(dst)
        assert img is not None
        assert img.shape[0] == 100 and img.shape[1] == 100

    def test_aspect_stretch_exact_dimensions(self):
        src = os.path.join(self.tmpdir, "any.png")
        dst = os.path.join(self.tmpdir, "stretch.png")
        _write_png(src, 60, 40)
        _base.core.convert_single_image(src, dst, 80, 80, "stretch", False)
        img = cv2.imread(dst)
        assert img is not None
        assert img.shape[0] == 80 and img.shape[1] == 80

    def test_delete_original_removes_source(self):
        src = os.path.join(self.tmpdir, "todelete.png")
        dst = os.path.join(self.tmpdir, "result.jpg")
        _write_png(src, 100, 100)
        _base.core.convert_single_image(src, dst, 100, 100, "stretch", True)
        assert not os.path.exists(src)
        assert os.path.exists(dst)


# ---------------------------------------------------------------------------
# get_files_by_extension
# ---------------------------------------------------------------------------

class TestGetFilesByExtension(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="base_core_gfe_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_returns_only_matching_extension(self):
        _write_png(os.path.join(self.tmpdir, "a.png"), 32, 32)
        _write_png(os.path.join(self.tmpdir, "b.jpg"), 32, 32)
        with open(os.path.join(self.tmpdir, "c.txt"), "w") as f:
            f.write("text")
        results = _base.core.get_files_by_extension(self.tmpdir, [".png"], False)
        assert len(results) == 1
        assert results[0].endswith(".png")

    def test_recursive_true_includes_subdirectory(self):
        subdir = os.path.join(self.tmpdir, "sub")
        os.makedirs(subdir)
        _write_png(os.path.join(self.tmpdir, "top.png"), 32, 32)
        _write_png(os.path.join(subdir, "nested.png"), 32, 32)
        flat = _base.core.get_files_by_extension(self.tmpdir, [".png"], False)
        rec = _base.core.get_files_by_extension(self.tmpdir, [".png"], True)
        assert len(flat) == 1
        assert len(rec) == 2

    def test_case_insensitive_extension_match(self):
        _write_png(os.path.join(self.tmpdir, "a.PNG"), 32, 32)
        _write_png(os.path.join(self.tmpdir, "b.Jpg"), 32, 32)
        results = _base.core.get_files_by_extension(
            self.tmpdir, [".png", ".jpg"], False
        )
        assert len(results) == 2

    def test_no_match_returns_empty(self):
        _write_png(os.path.join(self.tmpdir, "a.png"), 32, 32)
        results = _base.core.get_files_by_extension(self.tmpdir, [".webp"], False)
        assert results == []


# ---------------------------------------------------------------------------
# delete_path
# ---------------------------------------------------------------------------

class TestDeletePath(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="base_core_del_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_deletes_existing_file_returns_true(self):
        p = os.path.join(self.tmpdir, "f.txt")
        open(p, "w").close()
        result = _base.core.delete_path(p)
        assert result is True
        assert not os.path.exists(p)

    def test_deletes_directory_tree_returns_true(self):
        d = os.path.join(self.tmpdir, "nested")
        os.makedirs(d)
        open(os.path.join(d, "x.txt"), "w").close()
        result = _base.core.delete_path(d)
        assert result is True
        assert not os.path.exists(d)

    def test_nonexistent_path_returns_false(self):
        result = _base.core.delete_path(os.path.join(self.tmpdir, "no_such_file.txt"))
        assert result is False


# ---------------------------------------------------------------------------
# find_duplicate_images
# ---------------------------------------------------------------------------

class TestFindDuplicateImages(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="base_core_dup_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_identical_files_in_same_group(self):
        img = np.full((64, 64, 3), 100, dtype=np.uint8)
        for name in ["dup1.png", "dup2.png", "dup3.png"]:
            cv2.imwrite(os.path.join(self.tmpdir, name), img)
        diff = np.full((64, 64, 3), 200, dtype=np.uint8)
        cv2.imwrite(os.path.join(self.tmpdir, "different.png"), diff)
        groups = _base.core.find_duplicate_images(self.tmpdir)
        dup_group = [g for g in groups if len(g) >= 3]
        assert len(dup_group) == 1
        assert len(dup_group[0]) == 3

    def test_empty_directory_returns_empty(self):
        groups = _base.core.find_duplicate_images(self.tmpdir)
        assert groups == []


# ---------------------------------------------------------------------------
# find_similar_images_phash
# ---------------------------------------------------------------------------

class TestFindSimilarImagesPhash(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="base_core_phash_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_near_identical_images_grouped_together(self):
        base_img = np.full((64, 64, 3), 150, dtype=np.uint8)
        noisy = base_img.copy()
        noisy[0, 0] = [151, 151, 151]
        cv2.imwrite(os.path.join(self.tmpdir, "a.png"), base_img)
        cv2.imwrite(os.path.join(self.tmpdir, "b.png"), noisy)
        groups = _base.core.find_similar_images_phash(self.tmpdir, threshold=5)
        multi = [g for g in groups if len(g) >= 2]
        assert len(multi) >= 1

    def test_different_images_in_separate_groups(self):
        black = np.zeros((64, 64, 3), dtype=np.uint8)
        white = np.full((64, 64, 3), 255, dtype=np.uint8)
        cv2.imwrite(os.path.join(self.tmpdir, "black.png"), black)
        cv2.imwrite(os.path.join(self.tmpdir, "white.png"), white)
        groups = _base.core.find_similar_images_phash(self.tmpdir, threshold=5)
        assert len(groups) == 2


# ---------------------------------------------------------------------------
# merge_images_*
# ---------------------------------------------------------------------------

class TestMergeImages(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="base_core_merge_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _paths(self, *names):
        return [os.path.join(self.tmpdir, n) for n in names]

    def test_merge_horizontal_doubles_width(self):
        a = os.path.join(self.tmpdir, "a.png")
        b = os.path.join(self.tmpdir, "b.png")
        out = os.path.join(self.tmpdir, "h.png")
        _write_png(a, 50, 100)
        _write_png(b, 50, 100)
        _base.core.merge_images_horizontal([a, b], out)
        img = cv2.imread(out)
        assert img is not None
        assert img.shape[1] == 100
        assert img.shape[0] == 100

    def test_merge_horizontal_output_readable(self):
        a = os.path.join(self.tmpdir, "a.png")
        b = os.path.join(self.tmpdir, "b.png")
        out = os.path.join(self.tmpdir, "h2.png")
        _write_png(a, 32, 32)
        _write_png(b, 32, 32)
        _base.core.merge_images_horizontal([a, b], out)
        assert cv2.imread(out) is not None

    def test_merge_vertical_doubles_height(self):
        a = os.path.join(self.tmpdir, "va.png")
        b = os.path.join(self.tmpdir, "vb.png")
        out = os.path.join(self.tmpdir, "v.png")
        _write_png(a, 100, 50)
        _write_png(b, 100, 50)
        _base.core.merge_images_vertical([a, b], out)
        img = cv2.imread(out)
        assert img is not None
        assert img.shape[0] == 100
        assert img.shape[1] == 100

    def test_merge_grid_2x2(self):
        imgs = []
        for i in range(4):
            p = os.path.join(self.tmpdir, f"g{i}.png")
            _write_png(p, 50, 50, color=(i * 60, i * 60, i * 60))
            imgs.append(p)
        out = os.path.join(self.tmpdir, "grid.png")
        _base.core.merge_images_grid(imgs, out, cols=2)
        img = cv2.imread(out)
        assert img is not None
        assert img.shape[0] == 100
        assert img.shape[1] == 100


# ---------------------------------------------------------------------------
# wallpaper callables (no live display required)
# ---------------------------------------------------------------------------

def test_wallpaper_functions_accessible():
    assert callable(_base.core.set_wallpaper_gnome)
    assert callable(_base.core.evaluate_kde_script)
