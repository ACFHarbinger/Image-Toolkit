import pytest

from hie_middleware.models import MattingAdapter, ModelUnavailable
from hie_middleware.policies import BrushAssistantPolicy


def test_matting_adapter_reports_optional_runtime_without_importing_heavy_deps():
    adapter = MattingAdapter()
    assert not adapter.is_available()
    with pytest.raises(ModelUnavailable):
        adapter.propose("image.png")


def test_brush_policy_emits_deterministic_inspectable_proposal():
    policy = BrushAssistantPolicy()
    first = policy.propose({"document_id": "doc-1", "stroke": [1, 2, 3]})
    second = policy.propose({"stroke": [1, 2, 3], "document_id": "doc-1"})
    assert first == second
    assert first.action == "localized_tone"
    assert first.policy.task == "localized_retouching"
    policy.feedback(first.proposal_id, 0.5)
    with pytest.raises(ValueError):
        policy.feedback(first.proposal_id, 2.0)
