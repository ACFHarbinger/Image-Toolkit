"""Phase 1 crop/composition policy foundation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .base import Policy, PolicyProposal, PolicySpec


class CropCompositionPolicy(Policy):
    """Deterministic preview shell for a future composition policy."""

    spec = PolicySpec(
        name="crop-composition-optimizer",
        version="0.1",
        task="crop_composition",
        observation_schema="hie.crop_observation.v1",
        action_schema="hie.crop_action.v1",
    )

    def propose(self, observation: dict[str, Any]) -> PolicyProposal:
        encoded = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        proposal_id = hashlib.sha256(encoded.encode()).hexdigest()[:16]
        return PolicyProposal(
            proposal_id=proposal_id,
            action="crop",
            parameters={"center_x": 0.5, "center_y": 0.5, "scale": 1.0},
            policy=self.spec,
        )

    def feedback(self, proposal_id: str, reward: float) -> None:
        if not proposal_id:
            raise ValueError("proposal_id is required")
        if not -1.0 <= reward <= 1.0:
            raise ValueError("reward must be between -1 and 1")
