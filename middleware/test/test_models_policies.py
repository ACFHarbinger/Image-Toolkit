import pytest

from hie_middleware.models import (
    DeblurAdapter, MattingAdapter, ModelUnavailable, SuperResolutionAdapter,
    WatermarkRemovalAdapter,
)
from hie_middleware.policies import BrushAssistantPolicy, CropCompositionPolicy, GlobalTonePolicy


def test_matting_adapter_reports_optional_runtime_without_importing_heavy_deps():
    adapter = MattingAdapter()
    assert not adapter.is_available()
    with pytest.raises(ModelUnavailable):
        adapter.propose("image.png")


def test_super_resolution_adapter_is_optional_and_preserves_scale_metadata():
    adapter = SuperResolutionAdapter(scale=4)
    assert not adapter.is_available()
    assert adapter.spec.metadata["scale"] == 4
    with pytest.raises(ModelUnavailable):
        adapter.propose("image.png")

    with pytest.raises(ValueError):
        SuperResolutionAdapter(scale=1)


def test_deblur_adapter_is_optional_and_validates_method():
    adapter = DeblurAdapter(method="blind")
    assert adapter.spec.task == "deblur"
    assert not adapter.is_available()
    with pytest.raises(ModelUnavailable):
        adapter.propose("blurred.png")
    with pytest.raises(ValueError):
        DeblurAdapter(method="unknown")


def test_watermark_adapter_requires_mask_and_permission_before_runtime():
    adapter = WatermarkRemovalAdapter()
    with pytest.raises(ValueError, match="mask_ref"):
        adapter.propose("owned.png", permission_confirmed=True)
    with pytest.raises(PermissionError, match="ownership"):
        adapter.propose("owned.png", mask_ref="logo-mask.png")
    with pytest.raises(ModelUnavailable):
        adapter.propose("owned.png", mask_ref="logo-mask.png", permission_confirmed=True)


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


@pytest.mark.parametrize(
    ("policy_type", "task", "action"),
    [
        (GlobalTonePolicy, "global_tone_exposure", "adjust_exposure"),
        (CropCompositionPolicy, "crop_composition", "crop"),
    ],
)
def test_phase_one_policy_sequence_emits_stable_preview_proposals(policy_type, task, action):
    policy = policy_type()
    proposal = policy.propose({"document_id": "doc-1", "histogram": [0, 1, 2]})
    assert proposal.policy.task == task
    assert proposal.action == action
    assert proposal == policy.propose({"histogram": [0, 1, 2], "document_id": "doc-1"})
    policy.feedback(proposal.proposal_id, 0.0)
