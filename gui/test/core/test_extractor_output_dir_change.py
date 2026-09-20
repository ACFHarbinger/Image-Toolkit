"""Changing the extractor Output Directory must redirect where extractions
are written -- including queued items and re-queued recent extractions, which
used to keep writing to the previous path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gui.src.tabs.core.extractor_tab._video_session_history import (
    ExtractorVideoSessionHistoryController,
)

pytestmark = pytest.mark.gui


class TestRetargetPendingQueueItems:
    @staticmethod
    def _fn():
        from gui.src.tabs.core.extractor_tab._queue_panel import retarget_pending_queue_items

        return retarget_pending_queue_items

    def test_rewrites_output_dir_on_every_pending_item(self):
        queue = [{"output_dir": "/old", "id": 1}, {"output_dir": "/older", "id": 2}]
        assert self._fn()(queue, "/new") == 2
        assert [i["output_dir"] for i in queue] == ["/new", "/new"]

    def test_accepts_path_objects_and_counts_only_real_changes(self, tmp_path):
        queue = [{"output_dir": str(tmp_path)}, {"output_dir": "/old"}]
        assert self._fn()(queue, tmp_path) == 1

    def test_empty_queue_is_a_noop(self):
        assert self._fn()([], "/new") == 0


class _Tab:
    extraction_dir = "/current/out"


class _Host(ExtractorVideoSessionHistoryController):
    def __init__(self):
        super().__init__(_Tab())


def test_requeued_recent_run_uses_current_output_dir_not_the_recorded_one():
    cfg = _Host()._recent_run_to_queue_config(
        {"video_path": "/v/a.mp4", "start_ms": 0, "end_ms": 10, "output_dir": "/previous/out"}
    )
    assert cfg["output_dir"] == "/current/out"


class TestBrowseRetargetsQueue:
    def _make_tab(self):
        from gui.src.tabs.core.extractor_tab import ExtractorTab

        with (
            patch("gui.src.tabs.core.extractor_tab._media_player.QMediaPlayer"),
            patch("gui.src.tabs.core.extractor_tab._media_player.QAudioOutput"),
        ):
            tab = ExtractorTab()
        tab._media_player = MagicMock()
        return tab

    def test_browse_updates_directory_and_pending_queue(self, q_app, tmp_path):
        tab = self._make_tab()
        old_dir = tmp_path / "old"
        new_dir = tmp_path / "new"
        old_dir.mkdir()
        tab.extraction_dir = old_dir
        tab.extraction_queue = [
            {"type": "range", "video_path": "/v/a.mp4", "start_ms": 0, "end_ms": 5, "output_dir": str(old_dir)},
            {"type": "gif", "video_path": "/v/b.mp4", "start_ms": 0, "end_ms": 5, "output_dir": str(old_dir)},
        ]

        with patch(
            "gui.src.tabs.core.extractor_tab._video_session_config.QFileDialog.getExistingDirectory",
            return_value=str(new_dir),
        ):
            tab.browse_extraction_directory()

        assert tab.extraction_dir == new_dir
        assert tab.line_edit_extract_dir.text() == str(new_dir)
        assert [i["output_dir"] for i in tab.extraction_queue] == [str(new_dir)] * 2
        tab.close()

    def test_cancelled_browse_leaves_queue_untouched(self, q_app, tmp_path):
        tab = self._make_tab()
        tab.extraction_queue = [{"type": "range", "video_path": "/v/a.mp4", "start_ms": 0, "end_ms": 5, "output_dir": "/keep"}]

        with patch(
            "gui.src.tabs.core.extractor_tab._video_session_config.QFileDialog.getExistingDirectory",
            return_value="",
        ):
            tab.browse_extraction_directory()

        assert tab.extraction_queue[0]["output_dir"] == "/keep"
        tab.close()

    def test_in_process_items_keep_their_snapshot(self, q_app, tmp_path):
        tab = self._make_tab()
        new_dir = tmp_path / "new"
        tab.inprocess_items = [{"type": "range", "output_dir": "/running-here"}]

        with patch(
            "gui.src.tabs.core.extractor_tab._video_session_config.QFileDialog.getExistingDirectory",
            return_value=str(new_dir),
        ):
            tab.browse_extraction_directory()

        assert tab.inprocess_items[0]["output_dir"] == "/running-here"
        tab.close()
