"""Unit tests for backend.src.core.dir_phash_index (§7.6 bridge index)."""

import numpy as np
import pytest
from PIL import Image

from backend.src.core.dir_phash_index import (
    DirPhashIndex,
    compute_phash_bytes,
    compute_phash_file,
)


def _write_image(path, seed=0, size=(64, 64)):
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, (*size, 3), dtype=np.uint8)
    Image.fromarray(arr).save(path)
    return str(path)


@pytest.fixture()
def tree(tmp_path):
    root = tmp_path / "imgs"
    (root / "sub").mkdir(parents=True)
    a = _write_image(root / "a.png", seed=1)
    b = _write_image(root / "sub" / "b.jpg", seed=2)
    (root / "notes.txt").write_text("not an image")
    return root, a, b


class TestComputePhash:
    def test_bytes_and_file_agree(self, tree):
        _root, a, _b = tree
        with open(a, "rb") as fh:
            data = fh.read()
        assert compute_phash_bytes(data) == compute_phash_file(a)

    def test_bad_bytes_return_none(self):
        assert compute_phash_bytes(b"definitely not an image") is None

    def test_missing_file_returns_none(self, tmp_path):
        assert compute_phash_file(str(tmp_path / "nope.png")) is None


class TestDirPhashIndex:
    def _index(self, root, tmp_path, recursive=True):
        return DirPhashIndex(
            str(root), db_path=str(tmp_path / "idx.db"), recursive=recursive
        )

    def test_refresh_indexes_images_only(self, tree, tmp_path):
        root, _a, _b = tree
        idx = self._index(root, tmp_path)
        stats = idx.refresh()
        assert stats["computed"] == 2
        assert stats["total"] == 2
        assert stats["cold_scan"] is True
        assert idx.count() == 2

    def test_refresh_is_incremental(self, tree, tmp_path):
        root, _a, _b = tree
        idx = self._index(root, tmp_path)
        idx.refresh()
        stats = idx.refresh()
        assert stats["computed"] == 0
        assert stats["unchanged"] == 2
        assert stats["cold_scan"] is False

    def test_refresh_drops_deleted_files(self, tree, tmp_path):
        import os

        root, a, _b = tree
        idx = self._index(root, tmp_path)
        idx.refresh()
        os.remove(a)
        stats = idx.refresh()
        assert stats["removed"] == 1
        assert idx.count() == 1

    def test_non_recursive_skips_subdirs(self, tree, tmp_path):
        root, _a, _b = tree
        idx = self._index(root, tmp_path, recursive=False)
        stats = idx.refresh()
        assert stats["total"] == 1

    def test_query_finds_exact_duplicate(self, tree, tmp_path):
        root, a, _b = tree
        # Copy of a.png under a different name → Hamming distance 0
        import shutil

        dup = root / "a_copy.png"
        shutil.copy(a, dup)
        idx = self._index(root, tmp_path)
        idx.refresh()

        with open(a, "rb") as fh:
            matches = idx.query_bytes(fh.read(), threshold=0)
        paths = {m["path"] for m in matches}
        assert str(dup) in paths and a in paths
        assert all(m["hamming"] == 0 for m in matches)

    def test_query_respects_threshold(self, tree, tmp_path):
        root, a, _b = tree
        idx = self._index(root, tmp_path)
        idx.refresh()
        with open(a, "rb") as fh:
            data = fh.read()
        # Random-noise images are essentially uncorrelated: distance ~32 bits.
        matches = idx.query_bytes(data, threshold=5)
        assert [m["path"] for m in matches] == [a]

    def test_query_bytes_undecodable_returns_none(self, tree, tmp_path):
        root, _a, _b = tree
        idx = self._index(root, tmp_path)
        idx.refresh()
        assert idx.query_bytes(b"garbage") is None
