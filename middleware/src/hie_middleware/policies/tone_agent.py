"""Phase 1 global tone/exposure policy foundation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .base import Policy, PolicyProposal, PolicySpec


class GlobalTonePolicy(Policy):
    """Deterministic preview shell for a future trained tone policy."""

    spec = PolicySpec(
        name="global-tone-exposure-agent",
        version="0.1",
        task="global_tone_exposure",
        observation_schema="hie.tone_observation.v1",
        action_schema="hie.tone_action.v1",
    )

    def propose(self, observation: dict[str, Any]) -> PolicyProposal:
        encoded = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        proposal_id = hashlib.sha256(encoded.encode()).hexdigest()[:16]
        return PolicyProposal(
            proposal_id=proposal_id,
            action="adjust_exposure",
            parameters={"exposure": 0.0, "contrast": 0.0},
            policy=self.spec,
        )

    def feedback(self, proposal_id: str, reward: float) -> None:
        if not proposal_id:
            raise ValueError("proposal_id is required")
        if not -1.0 <= reward <= 1.0:
            raise ValueError("reward must be between -1 and 1")
