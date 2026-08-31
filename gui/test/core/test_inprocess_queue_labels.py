"""In Process queue row-label builder — pure logic, no Qt."""

from __future__ import annotations

from gui.src.tabs.core.extractor_tab._queue_management import (
    _ST_DONE,
    _ST_ERROR,
    _ST_PENDING,
    _ST_PROCESSING,
    _inprocess_row_label,
)

_ITEM = {"video_path": "/v/output12.mp4", "type": "gif", "start_ms": 490_000, "end_ms": 580_000}


def test_label_has_position_type_name_and_range():
    label = _inprocess_row_label(0, _ITEM, _ST_PENDING)
    assert "1." in label
    assert "[GIF]" in label
    assert "output12.mp4" in label
    assert "08:10" in label and "09:40" in label


def test_each_status_gets_a_distinct_icon():
    icons = {
        _inprocess_row_label(0, _ITEM, s)[0]
        for s in (_ST_PENDING, _ST_PROCESSING, _ST_DONE, _ST_ERROR)
    }
    assert len(icons) == 4


def test_open_ended_range_shows_End():
    label = _inprocess_row_label(2, {**_ITEM, "end_ms": -1}, _ST_PROCESSING)
    assert "3." in label
    assert "End)" in label


def test_missing_fields_do_not_raise():
    label = _inprocess_row_label(0, {}, "weird-unknown-status")
    assert "1." in label
    assert "[RANGE]" in label  # default type
