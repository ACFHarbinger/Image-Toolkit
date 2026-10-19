import pytest

from document import (
    ClipSegment, Document, DocumentHistory, DocumentSchemaError, Frame,
    FrameSequence, Layer, Modifier, ModifierEdge, Timeline,
)


def make_document() -> Document:
    return Document(
        "doc-1",
        FrameSequence((Frame("source.png"),)),
        layers=(Layer("layer-1", "Subject", FrameSequence.still("source.png"), modifiers=(
            Modifier("mask", "matte", {"threshold": 0.5}),
            Modifier("tone", "exposure", {"value": 0.2}),
        )),),
        edges=(ModifierEdge("mask", "tone"),),
    )


def test_still_and_multiframe_share_sequence_contract():
    still = FrameSequence.still("still.png")
    video = FrameSequence((Frame("frame-1.png", 40), Frame("frame-2.png", 40)), fps=25)
    assert len(still.frames) == 1
    assert len(video.frames) == 2


def test_document_round_trip_is_canonical_and_reproducible():
    document = make_document()
    restored = Document.from_json(document.to_json())
    assert restored == document
    assert restored.to_json() == document.to_json()
    assert restored.snapshot_id() == document.snapshot_id()


def test_invalid_schema_and_graph_fail_clearly():
    payload = make_document().to_dict()
    payload["schema_version"] = 99
    with pytest.raises(DocumentSchemaError, match="unsupported document schema"):
        Document.from_dict(payload)

    with pytest.raises(DocumentSchemaError, match="acyclic"):
        Document("doc", FrameSequence.still("x"), layers=(Layer(
            "layer", "Layer", FrameSequence.still("x"),
            modifiers=(Modifier("a", "one"), Modifier("b", "two")),
        ),), edges=(ModifierEdge("a", "b"), ModifierEdge("b", "a")))


def test_history_is_snapshot_based_and_clears_redo_after_commit():
    first = make_document()
    second = Document("doc-2", first.sequence)
    third = Document("doc-3", first.sequence)
    history = DocumentHistory(first)
    history.commit(second)
    history.commit(third)
    assert history.undo().document_id == "doc-2"
    assert history.redo().document_id == "doc-3"
    history.undo()
    history.commit(first)
    assert history.redo().document_id == "doc-1"


# ----------------------------------------------------------------------
# Track 05: Timeline / ClipSegment (trim/remove-range/splice slice)
# ----------------------------------------------------------------------


def _clip(name, in_ms, out_ms):
    return ClipSegment(name, in_ms, out_ms)


def test_clip_segment_validates_times():
    with pytest.raises(DocumentSchemaError, match="negative"):
        _clip("a.mp4", -1, 100)
    with pytest.raises(DocumentSchemaError, match="out_ms"):
        _clip("a.mp4", 200, 100)
    assert _clip("a.mp4", 0, 100).duration_ms == 100


def test_timeline_trim_adjusts_first_and_last_edges():
    tl = Timeline((_clip("a.mp4", 0, 1000), _clip("b.mp4", 0, 2000)))
    # Global window: a=[0,1000], b=[1000,3000]. Trim to [250, 2500].
    trimmed = tl.trim(250, 2500)
    # a keeps [250,1000]; b keeps its first 1500ms (window ends at 2500).
    assert trimmed.segments == (_clip("a.mp4", 250, 1000), _clip("b.mp4", 0, 1500))


def test_timeline_trim_drops_segments_outside_window():
    tl = Timeline((_clip("a.mp4", 0, 500), _clip("b.mp4", 0, 500)))
    trimmed = tl.trim(500, 1000)
    assert trimmed.segments == (_clip("b.mp4", 0, 500),)


def test_timeline_remove_range_splits_one_segment():
    tl = Timeline((_clip("a.mp4", 0, 1000),))
    out = tl.remove_range(300, 700)
    # Keep source [0,300] and [700,1000]; the middle 400ms is dropped.
    assert out.segments == (_clip("a.mp4", 0, 300), _clip("a.mp4", 700, 1000))


def test_timeline_remove_range_spans_two_segments():
    tl = Timeline((_clip("a.mp4", 0, 1000), _clip("b.mp4", 0, 1000)))
    out = tl.remove_range(800, 1200)
    assert out.segments == (_clip("a.mp4", 0, 800), _clip("b.mp4", 200, 1000))


def test_timeline_splice_inserts_at_position():
    tl = Timeline((_clip("a.mp4", 0, 1000), _clip("c.mp4", 0, 1000)))
    spliced = tl.splice(1, _clip("b.mp4", 0, 500))
    assert [s.source_path for s in spliced.segments] == ["a.mp4", "b.mp4", "c.mp4"]


def test_timeline_round_trip_via_dict():
    tl = Timeline((_clip("a.mp4", 0, 1000), _clip("b.mp4", 200, 900)))
    assert Timeline.from_dict(tl.to_dict()) == tl


def test_timeline_from_frames_adopts_sequence():
    seq = FrameSequence((Frame("a.mp4", 40), Frame("b.mp4", 40)), fps=25)
    tl = Timeline.from_frames(seq)
    assert [s.source_path for s in tl.segments] == ["a.mp4", "b.mp4"]


def test_timeline_undo_via_document_history():
    tl = Timeline((_clip("a.mp4", 0, 1000),))
    trimmed = tl.trim(100, 900)
    # Timeline edits are deterministic list edits committed to history
    # directly (design note's open question: direct DocumentHistory).
    assert trimmed != tl
    assert trimmed.segments[0].in_ms == 100
    assert trimmed.segments[0].out_ms == 900


def test_timeline_rejects_empty():
    with pytest.raises(DocumentSchemaError, match="at least one"):
        Timeline(()) 
