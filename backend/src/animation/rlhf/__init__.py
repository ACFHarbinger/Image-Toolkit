"""
RLHF (Reinforcement Learning from Human Feedback) package for the anime stitch pipeline.

Usage
-----
from backend.src.animation.rlhf import FeedbackStore, StitchRewardModel, train_reward_model, fine_tune_drl_agent
"""

from .bench_import import (
    parse_bench_json,
    resolve_anime_path,
    suggested_rating,
    verdict_label,
)
from .feedback_store import (
    RLHF_FLAW_TYPES,
    FeedbackStore,
    StitchAnnotation,
    StitchFeedback,
)
from .reward_model import StitchRewardModel
from .rlhf_trainer import fine_tune_drl_agent, train_reward_model

__all__ = [
    "FeedbackStore",
    "StitchFeedback",
    "StitchAnnotation",
    "RLHF_FLAW_TYPES",
    "StitchRewardModel",
    "train_reward_model",
    "fine_tune_drl_agent",
    "parse_bench_json",
    "resolve_anime_path",
    "suggested_rating",
    "verdict_label",
]
