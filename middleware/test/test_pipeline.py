import pytest

from hie_middleware.models import MattingAdapter, ModelUnavailable
from hie_middleware.policies import BrushAssistantPolicy
from hie_middleware.document import Document, DocumentHistory, FrameSequence
from hie_middleware.pipeline import (
    PipelineUnavailable,
    ProposalAcceptanceService,
    ProposalPipeline,
)


def test_pipeline_registers_capabilities_and_serializes_policy_proposals():
    pipeline = ProposalPipeline()
    pipeline.register_policy("brush", BrushAssistantPolicy())
    assert pipeline.capabilities() == {"models": [], "policies": ["brush"]}

    proposal = pipeline.policy_proposal("brush", {"document_id": "doc-1"})
    assert proposal.kind == "policy"
    assert proposal.to_dict()["proposal"]["action"] == "localized_tone"


def test_pipeline_keeps_optional_model_runtime_at_adapter_boundary():
    pipeline = ProposalPipeline()
    pipeline.register_model("matting", MattingAdapter())
    with pytest.raises(ModelUnavailable):
        pipeline.model_proposal("matting", "image.png")
    assert pipeline.capabilities()["models"] == ["matting"]


def test_pipeline_reports_missing_tools_and_invalid_names():
    pipeline = ProposalPipeline()
    with pytest.raises(PipelineUnavailable, match="not registered"):
        pipeline.policy_proposal("brush", {})
    with pytest.raises(ValueError):
        pipeline.register_policy(" brush", BrushAssistantPolicy())


def test_acceptance_records_a_proposal_through_document_history():
    pipeline = ProposalPipeline()
    pipeline.register_policy("brush", BrushAssistantPolicy())
    proposal = pipeline.policy_proposal("brush", {"document_id": "doc-1"})
    history = DocumentHistory(Document("doc-1", FrameSequence.still("image.png")))

    updated, record = ProposalAcceptanceService().accept(history, proposal)

    assert record.name == "brush"
    assert updated.metadata["accepted_proposals"][0]["name"] == "brush"
    assert history.undo().metadata == {}
    assert history.redo().snapshot_id() == updated.snapshot_id()
