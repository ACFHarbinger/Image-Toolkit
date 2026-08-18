"""Unit tests for the VideoEditorTab (Track 05 timeline editor)."""

from tabs.video_editor_tab import VideoEditorTab
from document import ClipSegment, Timeline


def _make_clip(tmp_path, name="clip.mp4"):
    p = tmp_path / name
    p.write_bytes(b"\x00" * 64)  # placeholder media file; only path matters
    return str(p)


def test_tab_initialization(q_app):
    tab = VideoEditorTab()
    assert tab.add_clip_button.text() == "Add clip…"
    assert tab.export_button.isEnabled() is False
    assert tab.timeline is None


def test_add_clip_starts_timeline_and_refreshes(q_app, tmp_path):
    tab = VideoEditorTab()
    clip = _make_clip(tmp_path)
    assert tab.add_clip(clip) is True
    assert tab.timeline is not None
    assert len(tab.timeline.segments) == 1
    assert tab.segment_list.count() == 1
    assert tab.export_button.isEnabled() is True


def test_splice_at_inserts_middle_segment(q_app, tmp_path):
    tab = VideoEditorTab()
    a = _make_clip(tmp_path, "a.mp4")
    b = _make_clip(tmp_path, "b.mp4")
    c = _make_clip(tmp_path, "c.mp4")
    tab.add_clip(a)
    tab.add_clip(c)
    assert tab.splice_at(1, b) is True
    sources = [s.source_path for s in tab.timeline.segments]
    assert sources == [a, b, c]
    assert tab.segment_list.count() == 3


def test_trim_and_undo_via_history(q_app, tmp_path):
    tab = VideoEditorTab()
    clip = _make_clip(tmp_path)
    tab.add_clip(clip, duration_ms=1000)
    tab.trim_start_spin.setValue(200)
    tab.trim_end_spin.setValue(800)
    tab.trim_timeline()
    assert tab.timeline.segments == (ClipSegment(clip, 200, 800),)
    tab.undo()
    assert tab.timeline.segments == (ClipSegment(clip, 0, 1000),)
    tab.redo()
    assert tab.timeline.segments == (ClipSegment(clip, 200, 800),)


def test_remove_range_splits_segment(q_app, tmp_path):
    tab = VideoEditorTab()
    clip = _make_clip(tmp_path)
    tab.add_clip(clip, duration_ms=1000)
    tab.remove_start_spin.setValue(300)
    tab.remove_end_spin.setValue(700)
    tab.remove_range()
    assert tab.timeline.segments == (ClipSegment(clip, 0, 300), ClipSegment(clip, 700, 1000))


def test_export_delegates_to_splicer(q_app, tmp_path):
    calls = []

    def fake_splicer(timeline, output):
        calls.append((timeline, output))
        return output

    tab = VideoEditorTab(splicer=fake_splicer)
    clip = _make_clip(tmp_path)
    tab.add_clip(clip)
    result = tab._run_splicer(str(tmp_path / "out.mp4"))
    assert result == str(tmp_path / "out.mp4")
    assert len(calls) == 1
    assert isinstance(calls[0][0], Timeline)


def test_missing_clip_rejected(q_app, tmp_path):
    tab = VideoEditorTab()
    assert tab.add_clip(str(tmp_path / "nope.mp4")) is False
    assert tab.timeline is None
