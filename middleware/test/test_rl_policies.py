"""Unit tests for GlobalTonePolicy and CropCompositionPolicy RL agents."""

import pytest
from hie_middleware.policies import (
    CropCompositionAgentPolicy,
    CropCompositionPolicy,
    GlobalToneAgentPolicy,
    GlobalTonePolicy,
)


def test_global_tone_policy_propose_and_feedback():
    policy = GlobalToneAgentPolicy()
    assert policy.spec.name == "global-tone-exposure-agent"

    obs = {"mean_lum": 200.0, "std_lum": 40.0}
    proposal = policy.propose(obs)

    assert proposal.action == "adjust_exposure"
    assert proposal.parameters["exposure"] < 0  # darkens bright input
    assert proposal.parameters["highlights"] == -0.1

    policy.feedback(proposal.proposal_id, 0.8)
    policy.feedback(proposal.proposal_id, 0.4)

    assert len(policy.get_reward_history()) == 2
    assert policy.average_reward == pytest.approx(0.6)


def test_crop_composition_policy_propose_and_feedback():
    policy = CropCompositionAgentPolicy()
    assert policy.spec.name == "crop-composition-optimizer"

    obs = {"width": 1920, "height": 1080, "saliency_center_x": 0.2, "saliency_center_y": 0.2}
    proposal = policy.propose(obs)

    assert proposal.action == "crop"
    assert "crop_bbox" in proposal.parameters
    assert proposal.parameters["center_x"] > 0.5  # shifts center right to align with rule of thirds

    policy.feedback(proposal.proposal_id, 0.9)
    assert policy.average_reward == 0.9


def test_invalid_feedback_rewards():
    policy = GlobalTonePolicy()
    proposal = policy.propose({"mean_lum": 128.0})

    with pytest.raises(ValueError, match="reward must be between -1 and 1"):
        policy.feedback(proposal.proposal_id, 2.5)

    with pytest.raises(ValueError, match="proposal_id is required"):
        policy.feedback("", 0.5)
