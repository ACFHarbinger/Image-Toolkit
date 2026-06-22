"""Tests for HITLSessionViewerDialog (S92)."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from gui.src.dialogs.hitl_session_viewer_dialog import (
    HITLSessionViewerDialog,
    _format_session_info,
    _list_sessions,
    _load_session_meta,
)

pytestmark = pytest.mark.gui


def _write_session(path: Path, checkpoints: dict, ts: float = 0.0) -> None:
    path.write_text(
        json.dumps({"version": 1, "timestamp": ts, "checkpoints": checkpoints}),
        encoding="utf-8",
    )


class TestListSessions:
    def test_empty_dir_returns_empty(self, tmp_path):
        assert _list_sessions(tmp_path) == []

    def test_nonexistent_dir_returns_empty(self, tmp_path):
        assert _list_sessions(tmp_path / "no_such") == []

    def test_lists_json_files(self, tmp_path):
        _write_session(tmp_path / "a.json", {}, ts=1000.0)
        _write_session(tmp_path / "b.json", {}, ts=2000.0)
        (tmp_path / "not_json.txt").write_text("x")
        paths = _list_sessions(tmp_path)
        names = [p.name for p in paths]
        assert set(names) == {"a.json", "b.json"}


class TestFormatSessionInfo:
    def test_format_shows_checkpoint_names(self, tmp_path):
        p = tmp_path / "s.json"
        _write_session(p, {"frames": {"selected_paths": []}, "edges": {"edges": []}})
        data = _load_session_meta(p)
        text = _format_session_info(data, p)
        assert "Frame selection" in text
        assert "Edge graph" in text

    def test_format_shows_file_size(self, tmp_path):
        p = tmp_path / "s.json"
        _write_session(p, {})
        data = _load_session_meta(p)
        text = _format_session_info(data, p)
        assert "KB" in text


class TestHITLSessionViewerDialog:
    def test_empty_session_dir_no_crash(self, q_app, tmp_path):
        dlg = HITLSessionViewerDialog(session_dir=tmp_path)
        assert dlg._list.count() == 0
        assert dlg.selected_path() is None

    def test_lists_sessions_in_dialog(self, q_app, tmp_path):
        _write_session(tmp_path / "s1.json", {"frames": {}})
        _write_session(tmp_path / "s2.json", {"edges": {}})
        dlg = HITLSessionViewerDialog(session_dir=tmp_path)
        assert dlg._list.count() == 2

    def test_selected_path_none_before_accept(self, q_app, tmp_path):
        _write_session(tmp_path / "s.json", {})
        dlg = HITLSessionViewerDialog(session_dir=tmp_path)
        dlg._list.setCurrentRow(0)
        # selected_path() is None until accept() is called via _on_load()
        assert dlg.selected_path() is None
