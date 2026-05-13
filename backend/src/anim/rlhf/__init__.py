"""
RLHF (Reinforcement Learning from Human Feedback) package for the anime stitch pipeline.

Usage
-----
from backend.src.anim.rlhf import FeedbackStore, StitchRewardModel, train_reward_model, fine_tune_drl_agent
"""

from .feedback_store import FLAW_TYPES, FeedbackStore, StitchAnnotation, StitchFeedback
from .reward_model import StitchRewardModel
from .rlhf_trainer import fine_tune_drl_agent, train_reward_model

__all__ = [
    "FeedbackStore",
    "StitchFeedback",
    "StitchAnnotation",
    "FLAW_TYPES",
    "StitchRewardModel",
    "train_reward_model",
    "fine_tune_drl_agent",
]
