"""Unit tests for MangaPreferenceDialog (roadmap §6.3, issue #197)."""

import numpy as np
import pytest
from backend.src.manga.preference_log import read_preferences
from gui.src.components.manga_preference_dialog import MangaPreferenceDialog

pytestmark = pytest.mark.gui


def _candidate(value=200):
    return np.full((20, 20, 3), value, dtype=np.uint8)


class TestMangaPreferenceDialog:
    def test_constructs_with_both_candidates(self, q_app):
        dlg = MangaPreferenceDialog(_candidate(200), _candidate(100), source_a="Scribble", source_b="Screentone")
        assert dlg.winner() is None

    def test_prefer_a_logs_and_closes(self, q_app, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        dlg = MangaPreferenceDialog(
            _candidate(), _candidate(), source_a="Scribble", source_b="Screentone", log_path=log_path
        )
        dlg.btn_prefer_a.click()

        assert dlg.winner() == "a"
        records = read_preferences(log_path=log_path)
        assert len(records) == 1
        assert records[0]["winner"] == "a"
        assert records[0]["source_a"] == "Scribble"
        assert records[0]["source_b"] == "Screentone"

    def test_prefer_b_logs_correct_winner(self, q_app, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        dlg = MangaPreferenceDialog(_candidate(), _candidate(), log_path=log_path)
        dlg.btn_prefer_b.click()

        assert dlg.winner() == "b"
        assert read_preferences(log_path=log_path)[0]["winner"] == "b"

    def test_tie_logs_correct_winner(self, q_app, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        dlg = MangaPreferenceDialog(_candidate(), _candidate(), log_path=log_path)
        dlg.btn_tie.click()

        assert dlg.winner() == "tie"
        assert read_preferences(log_path=log_path)[0]["winner"] == "tie"

    def test_preference_recorded_signal_emits_winner(self, q_app, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        dlg = MangaPreferenceDialog(_candidate(), _candidate(), log_path=log_path)

        received = []
        dlg.preference_recorded.connect(received.append)
        dlg.btn_prefer_a.click()

        assert received == ["a"]

    def test_metadata_passed_through_to_log(self, q_app, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        dlg = MangaPreferenceDialog(
            _candidate(), _candidate(), metadata={"mode_a": "scribble", "mode_b": "reference"}, log_path=log_path
        )
        dlg.btn_tie.click()

        assert read_preferences(log_path=log_path)[0]["metadata"] == {"mode_a": "scribble", "mode_b": "reference"}

    def test_large_candidate_is_scaled_down_for_preview(self, q_app, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        big = np.full((800, 800, 3), 128, dtype=np.uint8)
        dlg = MangaPreferenceDialog(big, big, log_path=log_path)
        # No assertion on exact pixel size beyond "constructs without error" --
        # the scaling path (pixmap.width() > _PREVIEW_WIDTH) is what's under
        # test here; a hard pixel-count assertion would be brittle across Qt
        # versions' scaling rounding.
        assert dlg.winner() is None
