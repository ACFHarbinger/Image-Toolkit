"""Tests for TagReviewDialog (new_features.md §4.4C, WD-tagger review queue)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from gui.src.components.dialogs.tag_review_dialog import TagReviewDialog

pytestmark = pytest.mark.gui


def _make_dialog(tmp_path, *paths) -> TagReviewDialog:
    """Construct a TagReviewDialog with the background worker's `start()`
    mocked out entirely — real inference would attempt a network call to
    Hugging Face Hub, which no unit test should ever do. Results are fed
    directly through the same signal handlers TagReviewWorker would emit."""
    image_paths = list(paths) or [tmp_path / "img_001.png"]
    for p in image_paths:
        p.write_bytes(b"\x89PNG\r\n\x1a\n")  # not a real PNG; preview path tolerates it
    with patch(
        "gui.src.helpers.models.tag_review_worker.TagReviewWorker.start"
    ):
        return TagReviewDialog(image_paths)


class TestTagReviewDialogBookkeeping:
    def test_on_result_and_finished_populate_order(self, tmp_path, q_app):
        dlg = _make_dialog(tmp_path)
        path = str(tmp_path / "img_001.png")
        entries = [
            ("1girl", 0.9, "general", True),
            ("smile", 0.4, "general", True),
            ("blush", 0.2, "general", False),  # review-zone tag, unchecked
        ]
        dlg._on_result(path, entries)
        dlg._on_tagging_finished()

        assert dlg._order == [path]
        assert dlg.accepted_tags(path) == ["1girl", "smile"]

    def test_checkbox_toggle_reflected_in_accepted_tags(self, tmp_path, q_app):
        dlg = _make_dialog(tmp_path)
        path = str(tmp_path / "img_001.png")
        dlg._on_result(
            path,
            [
                ("1girl", 0.9, "general", True),
                ("blush", 0.2, "general", False),
            ],
        )
        dlg._on_tagging_finished()

        # Promote the review-zone "blush" tag by checking its checkbox,
        # exactly what a human reviewer would do.
        blush_cb = next(
            cb for cb in dlg._checkboxes if cb.property("tag_name") == "blush"
        )
        blush_cb.setChecked(True)

        assert sorted(dlg.accepted_tags(path)) == ["1girl", "blush"]

    def test_custom_tag_added_and_saved(self, tmp_path, q_app):
        dlg = _make_dialog(tmp_path)
        path = str(tmp_path / "img_001.png")
        dlg._on_result(path, [("1girl", 0.9, "general", True)])
        dlg._on_tagging_finished()

        dlg._add_tag_edit.setText("my_custom_tag")
        dlg._add_custom_tag()

        assert sorted(dlg.accepted_tags(path)) == ["1girl", "my_custom_tag"]

    def test_save_all_writes_caption_sidecar_with_only_checked_tags(
        self, tmp_path, q_app
    ):
        dlg = _make_dialog(tmp_path)
        path_obj = tmp_path / "img_001.png"
        path = str(path_obj)
        dlg._on_result(
            path,
            [
                ("1girl", 0.9, "general", True),
                ("blush", 0.2, "general", False),  # left unchecked
            ],
        )
        dlg._on_tagging_finished()

        dlg._save_all()

        txt_path = path_obj.with_suffix(".txt")
        assert txt_path.exists()
        assert txt_path.read_text(encoding="utf-8") == "1girl"

    def test_trigger_prepended_when_set(self, tmp_path, q_app):
        img = tmp_path / "img_002.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\n")
        with patch(
            "gui.src.helpers.models.tag_review_worker.TagReviewWorker.start"
        ):
            dlg = TagReviewDialog([img], trigger="my_char")
        path = str(img)
        dlg._on_result(path, [("1girl", 0.9, "general", True)])
        dlg._on_tagging_finished()

        dlg._save_all()

        txt_path = img.with_suffix(".txt")
        assert txt_path.read_text(encoding="utf-8") == "my_char, 1girl"

    def test_navigation_preserves_edits(self, tmp_path, q_app):
        img_a = tmp_path / "a.png"
        img_b = tmp_path / "b.png"
        dlg = _make_dialog(tmp_path, img_a, img_b)

        dlg._on_result(str(img_a), [("tag_a", 0.9, "general", True)])
        dlg._on_result(str(img_b), [("tag_b", 0.9, "general", False)])
        dlg._on_tagging_finished()

        # Currently showing img_a; uncheck its only tag, then navigate.
        dlg._checkboxes[0].setChecked(False)
        dlg._go_next()
        assert dlg.accepted_tags(str(img_a)) == []

        # img_b's tag_b starts unchecked; check it, navigate back, and
        # confirm both edits stuck.
        dlg._checkboxes[0].setChecked(True)
        dlg._go_prev()
        assert dlg.accepted_tags(str(img_b)) == ["tag_b"]
