"""Smart-triage rule engine tests."""

import numpy as np

from backend.src.core.similarity.config import TriageRules
from backend.src.core.similarity.triage import auto_select


def _write_png(path, side):
    import cv2

    img = np.full((side, side, 3), 128, dtype=np.uint8)
    cv2.imwrite(str(path), img)


class TestAutoSelect:
    def test_resolution_priority(self, tmp_path):
        big, small = tmp_path / "big.png", tmp_path / "small.png"
        _write_png(big, 256)
        _write_png(small, 64)
        keeper, discards = auto_select([str(small), str(big)], TriageRules())
        assert keeper == str(big)
        assert discards == [str(small)]

    def test_format_priority_lossless_wins(self, tmp_path):
        import cv2

        img = np.random.default_rng(0).integers(0, 255, (128, 128, 3), dtype=np.uint8)
        png, jpg = tmp_path / "a.png", tmp_path / "a.jpg"
        cv2.imwrite(str(png), img)
        cv2.imwrite(str(jpg), img)
        rules = TriageRules(prefer_largest_file=False)
        keeper, _ = auto_select([str(jpg), str(png)], rules)
        assert keeper == str(png)

    def test_path_priority(self, tmp_path):
        arch = tmp_path / "Archive"
        down = tmp_path / "Downloads"
        arch.mkdir()
        down.mkdir()
        a, d = arch / "x.png", down / "x.png"
        _write_png(a, 64)
        _write_png(d, 64)
        keeper, discards = auto_select([str(d), str(a)], TriageRules())
        assert keeper == str(a)
        assert discards == [str(d)]

    def test_protected_never_discarded(self, tmp_path):
        big, small = tmp_path / "big.png", tmp_path / "small.png"
        _write_png(big, 256)
        _write_png(small, 64)
        keeper, discards = auto_select(
            [str(small), str(big)], TriageRules(), protected={str(small)}
        )
        assert str(small) not in discards

    def test_all_protected_returns_none(self, tmp_path):
        a, b = tmp_path / "a.png", tmp_path / "b.png"
        _write_png(a, 64)
        _write_png(b, 64)
        keeper, discards = auto_select(
            [str(a), str(b)], TriageRules(), protected={str(a), str(b)}
        )
        assert keeper is None and discards == []

    def test_missing_files_tolerated(self, tmp_path):
        real = tmp_path / "real.png"
        _write_png(real, 64)
        keeper, discards = auto_select([str(real), str(tmp_path / "ghost.png")])
        assert keeper == str(real)
