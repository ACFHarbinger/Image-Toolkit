"""Hardlink/symlink consolidation tests."""

import os

from backend.src.core.similarity.consolidate import consolidate_cluster


def _mk(path, data=b"x" * 1024):
    with open(path, "wb") as f:
        f.write(data)
    return str(path)


class TestConsolidate:
    def test_hardlink_replaces_duplicate(self, tmp_path):
        keeper = _mk(tmp_path / "keep.png")
        dup = _mk(tmp_path / "dup.png")
        res = consolidate_cluster(keeper, [dup], mode="hardlink")
        assert res.linked == [dup]
        assert res.bytes_reclaimed == 1024
        assert os.stat(keeper).st_ino == os.stat(dup).st_ino
        with open(dup, "rb") as f:
            assert f.read() == b"x" * 1024

    def test_symlink_mode(self, tmp_path):
        keeper = _mk(tmp_path / "keep.png")
        dup = _mk(tmp_path / "dup.png")
        res = consolidate_cluster(keeper, [dup], mode="symlink")
        assert res.linked == [dup]
        assert os.path.islink(dup)
        assert os.path.realpath(dup) == os.path.realpath(keeper)

    def test_already_linked_skipped(self, tmp_path):
        keeper = _mk(tmp_path / "keep.png")
        dup = str(tmp_path / "dup.png")
        os.link(keeper, dup)
        res = consolidate_cluster(keeper, [dup], mode="hardlink")
        assert res.linked == [] and res.skipped == [dup]

    def test_keeper_never_replaced(self, tmp_path):
        keeper = _mk(tmp_path / "keep.png")
        res = consolidate_cluster(keeper, [keeper], mode="hardlink")
        assert res.skipped == [keeper]
        assert not os.path.islink(keeper)

    def test_missing_keeper_errors(self, tmp_path):
        dup = _mk(tmp_path / "dup.png")
        res = consolidate_cluster(str(tmp_path / "ghost.png"), [dup])
        assert res.errors and res.linked == []
