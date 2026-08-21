"""Tests for backend/src/core/telemetry.py (debug/ instrumentation framework
added for the gallery-scan crash class in docs/TROUBLESHOOTING.md).
"""

from __future__ import annotations

import json

import pytest

from backend.src.core import telemetry


@pytest.fixture(autouse=True)
def _isolated_telemetry(tmp_path, monkeypatch):
    """Point telemetry at a scratch dir and force-enable it, restoring the
    previous global state afterwards -- telemetry is process-global by
    design (one file per pid), so tests must not leak state between them."""
    monkeypatch.setattr(telemetry, "TELEMETRY_DIR", tmp_path)
    previous_enabled = telemetry.is_enabled()
    telemetry.set_enabled(True)
    yield tmp_path
    telemetry.close()
    telemetry.set_enabled(previous_enabled)
    telemetry._file_path = None  # noqa: SLF001 -- reset for the next test's _ensure_file()


def _read_records(path):
    telemetry.close()  # ensure buffered content is flushed to disk
    files = list(path.glob("telemetry-*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines]


class TestEmit:
    def test_disabled_writes_nothing(self, tmp_path):
        telemetry.set_enabled(False)
        telemetry.emit("cat", "event")
        assert list(tmp_path.glob("telemetry-*.jsonl")) == []

    def test_enabled_writes_one_json_line(self, tmp_path):
        telemetry.emit("thread-lifecycle", "scanner.start", directory="/tmp/x")
        records = _read_records(tmp_path)
        assert len(records) == 1
        assert records[0]["category"] == "thread-lifecycle"
        assert records[0]["event"] == "scanner.start"
        assert records[0]["directory"] == "/tmp/x"

    def test_records_have_standard_fields(self, tmp_path):
        telemetry.emit("cat", "event")
        record = _read_records(tmp_path)[0]
        for key in ("t", "wall", "pid", "tid", "tname", "category", "event"):
            assert key in record

    def test_multiple_emits_append_in_order(self, tmp_path):
        telemetry.emit("cat", "first")
        telemetry.emit("cat", "second")
        telemetry.emit("cat", "third")
        events = [r["event"] for r in _read_records(tmp_path)]
        assert events == ["first", "second", "third"]

    def test_non_serializable_field_falls_back_to_str(self, tmp_path):
        class Weird:
            def __repr__(self):
                return "<Weird>"

        telemetry.emit("cat", "event", obj=Weird())
        record = _read_records(tmp_path)[0]
        assert record["obj"] == "<Weird>"


class TestSpan:
    def test_span_emits_start_and_end(self, tmp_path):
        with telemetry.span("native", "decode", path="/a.mp4"):
            pass
        events = [r["event"] for r in _read_records(tmp_path)]
        assert events == ["decode.start", "decode.end"]

    def test_span_end_has_duration(self, tmp_path):
        with telemetry.span("native", "decode"):
            pass
        end_record = _read_records(tmp_path)[1]
        assert end_record["duration_ms"] >= 0

    def test_span_records_error_and_reraises(self, tmp_path):
        with pytest.raises(ValueError), telemetry.span("native", "decode"):
            raise ValueError("boom")
        events = [r["event"] for r in _read_records(tmp_path)]
        assert events == ["decode.start", "decode.error"]
        assert "boom" in _read_records(tmp_path)[1]["error"]

    def test_span_disabled_is_a_plain_noop(self, tmp_path):
        telemetry.set_enabled(False)
        ran = False
        with telemetry.span("native", "decode"):
            ran = True
        assert ran is True
        assert list(tmp_path.glob("telemetry-*.jsonl")) == []

    def test_span_allocates_matching_span_ids(self, tmp_path):
        with telemetry.span("native", "decode"):
            telemetry.emit("native", "tick")
        start, tick, end = _read_records(tmp_path)
        assert start["span_id"] == end["span_id"] == tick["span_id"]
        assert "parent_span_id" not in start
        assert start["seq"] < tick["seq"] < end["seq"]
        assert start["runtime"] == "python"

    def test_nested_spans_set_parent_span_id(self, tmp_path):
        with telemetry.span("asp", "stage.composite"):
            with telemetry.span("asp", "stage.seam"):
                pass
        records = _read_records(tmp_path)
        outer_start, inner_start, inner_end, outer_end = records
        assert outer_start["span_id"] == outer_end["span_id"]
        assert inner_start["span_id"] == inner_end["span_id"]
        assert inner_start["parent_span_id"] == outer_start["span_id"]
        assert inner_start["span_id"] != outer_start["span_id"]

    def test_begin_end_span_pair(self, tmp_path):
        sid = telemetry.begin_span("asp", "stage.load")
        assert sid is not None
        telemetry.end_span("asp", "stage.load", span_id=sid)
        start, end = _read_records(tmp_path)
        assert start["span_id"] == end["span_id"] == sid
        assert end["event"] == "stage.load.end"

    def test_begin_span_disabled_is_none(self):
        telemetry.set_enabled(False)
        assert telemetry.begin_span("asp", "stage.load") is None


class TestEnableToggle:
    def test_set_enabled_false_then_true(self, tmp_path):
        telemetry.set_enabled(False)
        telemetry.emit("cat", "should-not-appear")
        telemetry.set_enabled(True)
        telemetry.emit("cat", "should-appear")
        events = [r["event"] for r in _read_records(tmp_path)]
        assert events == ["should-appear"]

    def test_env_var_truthy_values(self, monkeypatch):
        import importlib

        for value in ("1", "true", "YES", "on"):
            monkeypatch.setenv("IMAGE_TOOLKIT_TELEMETRY", value)
            reloaded = importlib.reload(telemetry)
            assert reloaded.is_enabled() is True
        monkeypatch.setenv("IMAGE_TOOLKIT_TELEMETRY", "0")
        reloaded = importlib.reload(telemetry)
        assert reloaded.is_enabled() is False
        importlib.reload(telemetry)  # restore a clean module for later tests
