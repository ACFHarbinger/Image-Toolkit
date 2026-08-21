"""Tests for TagReviewWorker (new_features.md §4.4C, WD-tagger review queue).

Note on mocking: `gui/test/conftest.py` deliberately stubs
`sys.modules["backend.src.models.wrappers"]` as a bare `MagicMock` (no
`__path__`) to keep GUI test collection fast — meaning `unittest.mock.patch`
can't resolve a dotted path *through* it (Python's import machinery needs a
real package there). Since the worker imports `WDTaggerWrapper` lazily
inside `run()`, we instead pre-register the exact leaf module name in
`sys.modules` ourselves — the import machinery finds it there directly
without ever needing `backend.src.models.wrappers` to be a real package.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest
from gui.src.helpers.models.tag_review_worker import TagReviewWorker

pytestmark = pytest.mark.gui

_MODULE_NAME = "backend.src.models.wrappers.wd_tagger_wrapper"


def _install_fake_wd_module(auto=None, review=None, available=True):
    """Register a fake wd_tagger_wrapper module in sys.modules and return
    (fake_module, wrapper_instance) for assertions. Caller must restore
    sys.modules afterward (see the `fake_wd_module` fixture)."""
    instance = MagicMock()
    instance.tag_with_review.return_value = (auto or [], review or [])
    cls = MagicMock()
    cls.is_available.return_value = available
    cls.return_value = instance

    fake_module = types.ModuleType(_MODULE_NAME)
    fake_module.WDTaggerWrapper = cls # pyrefly: ignore [missing-attribute]
    sys.modules[_MODULE_NAME] = fake_module
    return cls, instance


@pytest.fixture()
def fake_wd_module():
    previous = sys.modules.get(_MODULE_NAME)
    yield _install_fake_wd_module
    if previous is not None:
        sys.modules[_MODULE_NAME] = previous
    else:
        sys.modules.pop(_MODULE_NAME, None)


class TestTagReviewWorker:
    def test_skips_already_tagged_images(self, tmp_path, fake_wd_module):
        tagged = tmp_path / "tagged.png"
        tagged.write_bytes(b"x")
        tagged.with_suffix(".txt").write_text("already, done")
        untagged = tmp_path / "untagged.png"
        untagged.write_bytes(b"x")

        _cls, instance = fake_wd_module(
            auto=[{"tag": "1girl", "confidence": 0.9, "category": "general"}]
        )
        worker = TagReviewWorker([tagged, untagged])

        results = []
        worker.sig_result.connect(lambda p, e: results.append((p, e)))
        worker.run()

        assert len(results) == 1
        assert results[0][0] == str(untagged)
        instance.tag_with_review.assert_called_once_with(
            str(untagged), threshold=0.35, review_threshold=0.15
        )

    def test_splits_auto_and_review_tags_with_checked_flag(self, tmp_path, fake_wd_module):
        img = tmp_path / "img.png"
        img.write_bytes(b"x")
        fake_wd_module(
            auto=[{"tag": "1girl", "confidence": 0.9, "category": "general"}],
            review=[{"tag": "blush", "confidence": 0.2, "category": "general"}],
        )

        worker = TagReviewWorker([img])
        results = []
        worker.sig_result.connect(lambda p, e: results.append((p, e)))
        worker.run()

        _path, entries = results[0]
        assert ("1girl", 0.9, "general", True) in entries
        assert ("blush", 0.2, "general", False) in entries

    def test_unavailable_tagger_emits_error_and_returns(self, tmp_path, fake_wd_module):
        img = tmp_path / "img.png"
        img.write_bytes(b"x")
        fake_wd_module(available=False)

        worker = TagReviewWorker([img])
        errors = []
        worker.error.connect(errors.append)
        worker.run()

        assert len(errors) == 1
        assert "unavailable" in errors[0]

    def test_progress_signal_reflects_done_and_total(self, tmp_path, fake_wd_module):
        imgs = [tmp_path / f"img_{i}.png" for i in range(3)]
        for p in imgs:
            p.write_bytes(b"x")
        fake_wd_module(auto=[{"tag": "t", "confidence": 0.9, "category": "general"}])

        worker = TagReviewWorker(imgs)
        progress_calls = []
        worker.sig_progress.connect(lambda d, t: progress_calls.append((d, t)))
        worker.run()

        assert progress_calls == [(1, 3), (2, 3), (3, 3)]
