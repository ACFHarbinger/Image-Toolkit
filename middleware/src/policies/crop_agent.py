"""Phase 2/3 crop & composition RL optimizer policy."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from .base import Policy, PolicyProposal, PolicySpec


class CropCompositionPolicy(Policy):
    """RL policy for auto-cropping, visual weight balancing, and rule-of-thirds optimization."""

    spec = PolicySpec(
        name="crop-composition-optimizer",
        version="0.2",
        task="crop_composition",
        observation_schema="hie.crop_observation.v1",
        action_schema="hie.crop_action.v1",
    )

    def __init__(self, checkpoint_path: str | None = None) -> None:
        self.checkpoint_path = checkpoint_path
        self._rewards: List[Dict[str, Any]] = []

    def propose(self, observation: dict[str, Any]) -> PolicyProposal:
        encoded = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        proposal_id = hashlib.sha256(encoded.encode()).hexdigest()[:16]

        width = observation.get("width", 1920)
        height = observation.get("height", 1080)
        saliency_x = observation.get("saliency_center_x", 0.5)
        saliency_y = observation.get("saliency_center_y", 0.5)

        # Rule of thirds alignment target: nearest grid line at 0.33 or 0.67
        target_x = 0.33 if saliency_x < 0.5 else 0.67
        target_y = 0.33 if saliency_y < 0.5 else 0.67

        shift_x = target_x - saliency_x
        shift_y = target_y - saliency_y

        center_x = max(0.2, min(0.8, 0.5 + shift_x * 0.5))
        center_y = max(0.2, min(0.8, 0.5 + shift_y * 0.5))

        parameters = {
            "center_x": round(center_x, 3),
            "center_y": round(center_y, 3),
            "scale": 0.9,
            "crop_bbox": (
                int(width * (center_x - 0.45)),
                int(height * (center_y - 0.45)),
                int(width * 0.9),
                int(height * 0.9),
            ),
        }

        return PolicyProposal(
            proposal_id=proposal_id,
            action="crop",
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


CropCompositionAgentPolicy = CropCompositionPolicy

__all__ = ["CropCompositionPolicy", "CropCompositionAgentPolicy"]
