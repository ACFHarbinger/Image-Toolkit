"""Inspectable reinforcement-learning policy contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PolicySpec:
    name: str
    version: str
    task: str
    observation_schema: str
    action_schema: str


@dataclass(frozen=True)
class PolicyProposal:
    """A suggested action that must be previewed and explicitly accepted."""

    proposal_id: str
    action: str
    parameters: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    reward_hint: float = 0.0
    policy: PolicySpec | None = None


class Policy:
    spec: PolicySpec

    def propose(self, observation: dict[str, Any]) -> PolicyProposal:
        raise NotImplementedError

    def feedback(self, proposal_id: str, reward: float) -> None:
        raise NotImplementedError

