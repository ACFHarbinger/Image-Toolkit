from document import Document, FrameSequence
from pipeline import PipelineSession
from jobs import JobStatus


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


def test_pipeline_session_dispatches_restoration_through_injected_pipeline():
    calls = []

    class FakeRestoration:
        def submit(self, operation, input_ref, *, backend, options):
            calls.append((operation, input_ref, backend, options))
            from jobs import submit_job

            return submit_job(lambda _token, _report: None)

    session = PipelineSession(
        Document("doc-1", FrameSequence.still("image.png")),
        restoration=FakeRestoration(),
    )
    handle = session.submit_restoration(
        "deblur", "image.png", backend="pillow", options={"strength": 0.5}
    )
    assert handle.result(5).status is JobStatus.SUCCEEDED
    assert calls == [("deblur", "image.png", "pillow", {"strength": 0.5})]
