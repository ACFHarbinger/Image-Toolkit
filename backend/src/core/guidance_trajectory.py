"""Bounded guidance conversation for the Review loop (#754).

After Diff & Apply (#752) re-queues a labeled variant, the next advisor
call must see what was tried and whether it helped — not just the
current graph. This module is the torch-free record of that trajectory:

- each step stores original feedback, applied node/field/old→new/reason,
  expected effect, the parent→variant prompt ids, and the user's verdict
- storage is capped (first step + latest) so the conversation cannot
  grow without bound
- after a configurable number of unresolved iterations the payload
  steers toward a structural change instead of another parameter tweak

Persisted on the variant ``ComfyRunRecord`` (``guidance_trajectory``
surface field) and optionally as a sidecar JSON next to the variant
workflow. Verdicts are the same class of measured preference as Gate D.7
tournament votes.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

VERDICTS = ("better", "same", "worse", "unsure")
MAX_STORED_STEPS = 5
STRUCTURAL_AFTER = 3
STRUCTURAL_HINT = (
    "parameter tuning hasn't resolved this — consider retraining with augmented data"
)
SIDECAR_SUFFIX = "_trajectory.json"
_SAFE_ID = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class AppliedChange:
    """One applied suggestion row (node / field / old → new / reason)."""

    node_id: str
    input_name: str
    from_value: Any
    to_value: Any
    reason: str = ""

    def summary(self) -> str:
        return (
            f"{self.input_name}: {self.from_value} → {self.to_value} "
            f"(node #{self.node_id})"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "input_name": self.input_name,
            "from": self.from_value,
            "to": self.to_value,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppliedChange:
        return cls(
            node_id=str(data.get("node_id", "")),
            input_name=str(data.get("input_name") or data.get("input") or ""),
            from_value=data.get("from", data.get("from_value")),
            to_value=data.get("to", data.get("to_value")),
            reason=str(data.get("reason") or ""),
        )


@dataclass(frozen=True)
class TrajectoryStep:
    """One apply → re-queue → evaluate turn."""

    parent_prompt_id: str
    variant_prompt_id: str | None = None
    feedback: str = ""
    expected: str = ""
    applied: tuple[AppliedChange, ...] = ()
    verdict: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_prompt_id": self.parent_prompt_id,
            "variant_prompt_id": self.variant_prompt_id,
            "feedback": self.feedback,
            "expected": self.expected,
            "applied": [change.to_dict() for change in self.applied],
            "verdict": self.verdict,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrajectoryStep:
        raw = data.get("applied") if isinstance(data, dict) else None
        applied = tuple(
            AppliedChange.from_dict(item)
            for item in raw
            if isinstance(item, dict)
        ) if isinstance(raw, list) else ()
        verdict = data.get("verdict")
        return cls(
            parent_prompt_id=str(data.get("parent_prompt_id") or ""),
            variant_prompt_id=_opt_str(data.get("variant_prompt_id")),
            feedback=str(data.get("feedback") or ""),
            expected=str(data.get("expected") or ""),
            applied=applied,
            verdict=verdict if verdict in VERDICTS else None,
        )


@dataclass(frozen=True)
class GuidanceTrajectory:
    """Conversation memory for one parent→variant chain."""

    root_prompt_id: str
    steps: tuple[TrajectoryStep, ...] = ()
    max_steps: int = MAX_STORED_STEPS

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_prompt_id": self.root_prompt_id,
            "steps": [step.to_dict() for step in self.steps],
            "max_steps": self.max_steps,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> GuidanceTrajectory:
        if not isinstance(data, dict):
            return cls(root_prompt_id="")
        raw = data.get("steps")
        steps = tuple(
            TrajectoryStep.from_dict(item)
            for item in raw
            if isinstance(item, dict)
        ) if isinstance(raw, list) else ()
        max_steps = data.get("max_steps", MAX_STORED_STEPS)
        if type(max_steps) is not int or not 2 <= max_steps <= MAX_STORED_STEPS:
            max_steps = MAX_STORED_STEPS
        return cls(
            root_prompt_id=str(data.get("root_prompt_id") or ""),
            steps=truncate_steps(steps, max_steps),
            max_steps=max_steps,
        )

    @property
    def latest(self) -> TrajectoryStep | None:
        return self.steps[-1] if self.steps else None


def changes_from_verdicts(verdicts) -> tuple[AppliedChange, ...]:
    """Lift #751/#752 suggestion rows into applied-change records."""
    out: list[AppliedChange] = []
    for verdict in verdicts or ():
        change = getattr(verdict, "change", None)
        if change is None:
            continue
        out.append(
            AppliedChange(
                node_id=str(getattr(change, "node_id", "")),
                input_name=str(getattr(change, "input_name", "")),
                from_value=getattr(change, "from_value", None),
                to_value=getattr(change, "to_value", None),
                reason=str(getattr(change, "reason", "") or ""),
            )
        )
    return tuple(out)


def expected_effect(changes: tuple[AppliedChange, ...]) -> str:
    reasons = [change.reason.strip() for change in changes if change.reason.strip()]
    return "; ".join(reasons)


def truncate_steps(
    steps: tuple[TrajectoryStep, ...],
    max_steps: int = MAX_STORED_STEPS,
) -> tuple[TrajectoryStep, ...]:
    """Keep the first feedback and the latest state; drop the middle."""
    max_steps = max(2, min(MAX_STORED_STEPS, max_steps))
    if len(steps) <= max_steps:
        return steps
    return (steps[0],) + steps[-(max_steps - 1) :]


def append_step(traj: GuidanceTrajectory, step: TrajectoryStep) -> GuidanceTrajectory:
    root = traj.root_prompt_id or step.parent_prompt_id
    return replace(
        traj,
        root_prompt_id=root,
        steps=truncate_steps(traj.steps + (step,), traj.max_steps),
    )


def bind_variant(traj: GuidanceTrajectory, variant_prompt_id: str) -> GuidanceTrajectory:
    """Stamp the queued prompt id onto the latest step."""
    if not traj.steps or not variant_prompt_id:
        return traj
    last = traj.steps[-1]
    if last.variant_prompt_id == variant_prompt_id:
        return traj
    return replace(traj, steps=traj.steps[:-1] + (replace(last, variant_prompt_id=variant_prompt_id),))


def record_verdict(
    traj: GuidanceTrajectory,
    verdict: str,
    *,
    variant_prompt_id: str | None = None,
    feedback: str | None = None,
) -> GuidanceTrajectory:
    """Store a Better/Same/Worse/Unsure evaluation on the matching step."""
    if verdict not in VERDICTS:
        raise ValueError(f"unknown verdict {verdict!r}")
    if not traj.steps:
        return traj
    idx = len(traj.steps) - 1
    if variant_prompt_id:
        for i, step in enumerate(traj.steps):
            if step.variant_prompt_id == variant_prompt_id:
                idx = i
                break
        else:
            return traj
    step = traj.steps[idx]
    updated = replace(step, verdict=verdict)
    extra = (feedback or "").strip()
    if extra and not step.feedback:
        updated = replace(updated, feedback=extra)
    steps = list(traj.steps)
    steps[idx] = updated
    return replace(traj, steps=tuple(steps))


def unresolved_count(traj: GuidanceTrajectory) -> int:
    """Evaluated steps that did not resolve the complaint (not better)."""
    return sum(1 for step in traj.steps if step.verdict in ("same", "worse", "unsure"))


def should_steer_structural(
    traj: GuidanceTrajectory,
    *,
    after: int = STRUCTURAL_AFTER,
) -> bool:
    return unresolved_count(traj) >= after


def format_for_advisor(traj: GuidanceTrajectory) -> dict[str, Any]:
    """Payload the next VLM/advisor call receives — the trajectory, not just now."""
    steer = should_steer_structural(traj)
    return {
        "root_prompt_id": traj.root_prompt_id,
        "steps": [step.to_dict() for step in traj.steps],
        "unresolved": unresolved_count(traj),
        "steer_structural": steer,
        "hint": STRUCTURAL_HINT if steer else None,
    }


def build_requeue_trajectory(
    *,
    existing: GuidanceTrajectory | None,
    parent_prompt_id: str | None,
    selected,
    feedback: str = "",
) -> GuidanceTrajectory:
    """Append one apply-step from the checked Diff & Apply rows."""
    parent = parent_prompt_id or ""
    base = existing if existing is not None else GuidanceTrajectory(root_prompt_id=parent)
    if not base.root_prompt_id:
        base = replace(base, root_prompt_id=parent)
    changes = changes_from_verdicts(selected)
    return append_step(
        base,
        TrajectoryStep(
            parent_prompt_id=parent,
            feedback=feedback.strip(),
            expected=expected_effect(changes),
            applied=changes,
        ),
    )


def trajectory_sidecar_path(directory: str | Path, root_prompt_id: str) -> Path:
    stem = _SAFE_ID.sub("_", root_prompt_id or "workflow") or "workflow"
    return Path(directory) / f"{stem}{SIDECAR_SUFFIX}"


def save_trajectory(path: str | Path, traj: GuidanceTrajectory) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=target.parent, prefix=target.name, suffix=".tmp")
    tmp = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(traj.to_dict(), handle, indent=2)
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return target


def load_trajectory(path: str | Path) -> GuidanceTrajectory | None:
    target = Path(path)
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return GuidanceTrajectory.from_dict(data)


def trajectory_from_record(record: Any) -> GuidanceTrajectory | None:
    raw = getattr(record, "guidance_trajectory", None)
    if isinstance(raw, dict):
        return GuidanceTrajectory.from_dict(raw)
    return None


def load_existing_trajectory(manager: Any, source_id: str | None) -> GuidanceTrajectory:
    parent = source_id or ""
    empty = GuidanceTrajectory(root_prompt_id=parent)
    if not parent or manager is None:
        return empty
    getter = getattr(manager, "get_run", None)
    if not callable(getter):
        return empty
    record = getter(parent)
    loaded = trajectory_from_record(record)
    return loaded if loaded is not None else empty


def _opt_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
