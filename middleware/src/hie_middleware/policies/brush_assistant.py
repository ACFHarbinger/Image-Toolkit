"""Phase 1 localized-retouching policy foundation."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .base import Policy, PolicyProposal, PolicySpec


class BrushAssistantPolicy(Policy):
    """Deterministic proposal shell for a future trained RL policy.

    It intentionally emits a safe, inspectable action and does not mutate the
    document. A Gymnasium/PyTorch implementation can replace ``propose`` while
    preserving this contract.
    """

    spec = PolicySpec(
        name="localized-retouching-brush-assistant",
        version="0.1",
        task="localized_retouching",
        observation_schema="hie.brush_observation.v1",
        action_schema="hie.brush_action.v1",
    )

    def propose(self, observation: dict[str, Any]) -> PolicyProposal:
        payload = json.dumps(observation, sort_keys=True, separators=(",", ":"))
        proposal_id = hashlib.sha256(payload.encode()).hexdigest()[:16]
        return PolicyProposal(
            proposal_id=proposal_id,
            action="localized_tone",
            parameters={"strength": 0.1, "radius": 24.0},
            confidence=0.0,
            reward_hint=0.0,
            policy=self.spec,
        )

    def feedback(self, proposal_id: str, reward: float) -> None:
        if not proposal_id:
            raise ValueError("proposal_id is required")
        if not -1.0 <= reward <= 1.0:
            raise ValueError("reward must be between -1 and 1")

