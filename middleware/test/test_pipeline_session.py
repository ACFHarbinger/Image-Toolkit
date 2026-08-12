from hie_middleware.document import Document, FrameSequence
from hie_middleware.pipeline import PipelineSession


def test_pipeline_session_previews_then_accepts_into_undoable_history():
    session = PipelineSession(Document("doc-1", FrameSequence.still("image.png")))
    proposal = session.preview_policy("brush-assistant", {"stroke": [1, 2]})
    before = session.document.snapshot_id()
    record = session.accept(proposal)

    assert record.name == "brush-assistant"
    assert session.document.snapshot_id() != before
    assert session.document.metadata["accepted_proposals"]
    assert session.history.undo().snapshot_id() == before


def test_pipeline_session_uses_default_capability_registry():
    session = PipelineSession(Document("doc-1", FrameSequence.still("image.png")))
    assert "global-tone" in session.pipeline.capabilities()["policies"]
    assert "alpha-matting" in session.pipeline.capabilities()["models"]
