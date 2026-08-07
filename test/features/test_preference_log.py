import json

import pytest

from features.preference_log import log_preference, read_preferences


class TestLogPreference:
    def test_appends_and_returns_record(self, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        record = log_preference("a.png", "b.png", "a", log_path=log_path)
        assert record["source_a"] == "a.png"
        assert record["source_b"] == "b.png"
        assert record["winner"] == "a"
        assert "timestamp" in record

    def test_creates_parent_directories(self, tmp_path):
        log_path = tmp_path / "nested" / "dir" / "prefs.jsonl"
        log_preference("a.png", "b.png", "tie", log_path=log_path)
        assert log_path.exists()

    def test_multiple_votes_append_as_separate_lines(self, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        log_preference("a1.png", "b1.png", "a", log_path=log_path)
        log_preference("a2.png", "b2.png", "b", log_path=log_path)
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["winner"] == "a"
        assert json.loads(lines[1])["winner"] == "b"

    def test_metadata_stored_as_is(self, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        record = log_preference(
            "a.png",
            "b.png",
            "b",
            metadata={"mode_a": "scribble", "mode_b": "screentone"},
            log_path=log_path,
        )
        assert record["metadata"] == {"mode_a": "scribble", "mode_b": "screentone"}

    def test_no_metadata_defaults_to_empty_dict(self, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        record = log_preference("a.png", "b.png", "tie", log_path=log_path)
        assert record["metadata"] == {}

    def test_invalid_winner_raises(self, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        with pytest.raises(ValueError, match="winner must be"):
            log_preference("a.png", "b.png", "c", log_path=log_path)


class TestReadPreferences:
    def test_missing_file_returns_empty_list(self, tmp_path):
        log_path = tmp_path / "does_not_exist.jsonl"
        assert read_preferences(log_path=log_path) == []

    def test_reads_back_all_records_in_order(self, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        log_preference("a1.png", "b1.png", "a", log_path=log_path)
        log_preference("a2.png", "b2.png", "b", log_path=log_path)
        log_preference("a3.png", "b3.png", "tie", log_path=log_path)

        records = read_preferences(log_path=log_path)
        assert len(records) == 3
        assert [r["winner"] for r in records] == ["a", "b", "tie"]

    def test_ignores_blank_lines(self, tmp_path):
        log_path = tmp_path / "prefs.jsonl"
        log_preference("a.png", "b.png", "a", log_path=log_path)
        with log_path.open("a") as f:
            f.write("\n\n")

        assert len(read_preferences(log_path=log_path)) == 1
