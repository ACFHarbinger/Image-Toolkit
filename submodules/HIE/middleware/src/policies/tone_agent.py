"""Phase 2/3 global tone/exposure RL retouching agent policy."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from .base import Policy, PolicyProposal, PolicySpec


class GlobalTonePolicy(Policy):
    """RL policy for automated global color grading, exposure balancing, and dynamic range optimization."""

    spec = PolicySpec(
        name="global-tone-exposure-agent",
        version="0.2",
        task="global_tone_exposure",
        observation_schema="hie.tone_observation.v1",
        action_schema="hie.tone_action.v1",
    )

    def __init__(self, checkpoint_path: str | None = None) -> None:
        self.checkpoint_path = checkpoint_path
        self._rewards: List[Dict[str, Any]] = []

    def propose(self, observation: dict[str, Any]) -> PolicyProposal:
        encoded = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        proposal_id = hashlib.sha256(encoded.encode()).hexdigest()[:16]

        mean_lum = observation.get("mean_lum", 128.0)
        std_lum = observation.get("std_lum", 50.0)

        # RL policy heuristic calculation for exposure and contrast adjustments
        exposure_shift = round((128.0 - mean_lum) / 128.0, 2)
        contrast_boost = round((60.0 - std_lum) / 100.0, 2) if std_lum < 60.0 else 0.0

        parameters = {
            "exposure": exposure_shift,
            "contrast": contrast_boost,
            "vibrance": 0.05,
            "highlights": -0.1 if mean_lum > 180 else 0.0,
            "shadows": 0.1 if mean_lum < 80 else 0.0,
        }

        return PolicyProposal(
            proposal_id=proposal_id,
            action="adjust_exposure",
            parameters=parameters,
            policy=self.spec,
        )

    def feedback(self, proposal_id: str, reward: float) -> None:
        if not proposal_id:
            raise ValueError("proposal_id is required")
        if not -1.0 <= reward <= 1.0:
            raise ValueError("reward must be between -1 and 1")
        self._rewards.append({"proposal_id": proposal_id, "reward": reward})

    def get_reward_history(self) -> List[Dict[str, Any]]:
        return list(self._rewards)

    @property
    def average_reward(self) -> float:
        if not self._rewards:
            return 0.0
        return sum(r["reward"] for r in self._rewards) / len(self._rewards)


GlobalToneAgentPolicy = GlobalTonePolicy

__all__ = ["GlobalTonePolicy", "GlobalToneAgentPolicy"]
