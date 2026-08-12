"""Dependency-light proposal orchestrator for HIE assistance tools.

The orchestrator deliberately stops at an inspectable proposal. Applying an
operation belongs to a later document/history service and must be explicit in
the UI. Optional model runtimes are therefore isolated behind the adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models import ModelAdapter, ModelProposal
from ..policies import Policy, PolicyProposal


class PipelineUnavailable(RuntimeError):
    """Raised when a requested model or policy is not registered."""


@dataclass(frozen=True)
class PipelineProposal:
    """Tagged union envelope suitable for frontend/IPC serialization."""

    kind: str
    name: str
    proposal: ModelProposal | PolicyProposal

    def to_dict(self) -> dict[str, Any]:
        value = self.proposal
        if isinstance(value, ModelProposal):
            payload = {
                "operation": value.operation,
                "confidence": value.confidence,
                "payload": value.payload,
                "model": value.model.name if value.model else None,
            }
        else:
            payload = {
                "proposal_id": value.proposal_id,
                "action": value.action,
                "parameters": value.parameters,
                "confidence": value.confidence,
                "reward_hint": value.reward_hint,
                "policy": value.policy.name if value.policy else None,
            }
        return {"kind": self.kind, "name": self.name, "proposal": payload}


class ProposalPipeline:
    """Registry and invocation boundary shared by both HIE frontends."""

    def __init__(self) -> None:
        self._models: dict[str, ModelAdapter] = {}
        self._policies: dict[str, Policy] = {}

    def register_model(self, name: str, adapter: ModelAdapter) -> None:
        self._models[_validate_name(name)] = adapter

    def register_policy(self, name: str, policy: Policy) -> None:
        self._policies[_validate_name(name)] = policy

    def model_proposal(self, name: str, input_ref: str, **options: Any) -> PipelineProposal:
        adapter = self._models.get(name)
        if adapter is None:
            raise PipelineUnavailable(f"model is not registered: {name}")
        return PipelineProposal("model", name, adapter.propose(input_ref, **options))

    def policy_proposal(
        self, name: str, observation: dict[str, Any]
    ) -> PipelineProposal:
        policy = self._policies.get(name)
        if policy is None:
            raise PipelineUnavailable(f"policy is not registered: {name}")
        return PipelineProposal("policy", name, policy.propose(observation))

    def capabilities(self) -> dict[str, list[str]]:
        return {
            "models": sorted(self._models),
            "policies": sorted(self._policies),
        }


def _validate_name(name: str) -> str:
    if not name or name.strip() != name:
        raise ValueError("registry names must be non-empty and trimmed")
    return name
