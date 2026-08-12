import pytest

from hie_middleware.document import (
    Document, DocumentHistory, DocumentSchemaError, Frame, FrameSequence,
    Layer, Modifier, ModifierEdge,
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
