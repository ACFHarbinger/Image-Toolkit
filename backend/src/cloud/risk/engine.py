"""Data-driven risk rules (#830): conditions over a flat context → findings.

Pure and Qt-free; the UI binds findings to form fields (recolour by severity,
⚠ message, grey out ``disables``) and the backend re-runs the same
evaluation at submit.

Condition grammar::

    {field: a.b, op: eq|ne|gt|gte|lt|lte|in|not_in|truthy|falsy, value: X}
    {field: a.b, op: gt, ref: c.d}        # compare with another context value
    {all: [cond, ...]} | {any: [cond, ...]} | {not: cond}

A missing field never matches (it does not raise), so a rule written for a
fact some providers don't report simply stays quiet for them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml

SEED_PATH = Path(__file__).with_name("rules.yaml")
_MISSING = object()
_PLACEHOLDER = re.compile(r"\{([A-Za-z0-9_.]+)\}")


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


class RuleKind(str, Enum):
    CAPABILITY = "capability"
    POLICY = "policy"


class RuleError(ValueError):
    pass


_OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "truthy": lambda a, _b: bool(a),
    "falsy": lambda a, _b: not a,
}


def _check_condition(cond: Any, rule_id: str) -> None:
    if not isinstance(cond, Mapping):
        raise RuleError(f"{rule_id}: condition must be a mapping")
    if "all" in cond or "any" in cond:
        for sub in cond.get("all", cond.get("any")) or ():
            _check_condition(sub, rule_id)
    elif "not" in cond:
        _check_condition(cond["not"], rule_id)
    else:
        if "field" not in cond or cond.get("op") not in _OPS:
            raise RuleError(f"{rule_id}: leaf needs `field` and an op in {sorted(_OPS)}")


def evaluate_condition(cond: Mapping[str, Any], ctx: Mapping[str, Any]) -> bool:
    if "all" in cond:
        return all(evaluate_condition(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(evaluate_condition(c, ctx) for c in cond["any"])
    if "not" in cond:
        return not evaluate_condition(cond["not"], ctx)
    left = ctx.get(cond["field"], _MISSING)
    if left is _MISSING or left is None:
        return False
    if "ref" in cond:
        right = ctx.get(cond["ref"], _MISSING)
        if right is _MISSING or right is None:
            return False
    else:
        right = cond.get("value")
    try:
        return bool(_OPS[cond["op"]](left, right))
    except TypeError:
        return False


@dataclass(frozen=True)
class Rule:
    id: str
    kind: RuleKind
    severity: Severity
    when: Mapping[str, Any]
    message: str
    targets: Tuple[str, ...] = ()
    disables: Tuple[str, ...] = ()
    requires_ack: bool = False
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Rule":
        rule_id = str(data.get("id", ""))
        if not rule_id:
            raise RuleError("rule without id")
        try:
            kind, severity = RuleKind(data["kind"]), Severity(data["severity"])
        except (KeyError, ValueError) as exc:
            raise RuleError(f"{rule_id}: bad kind/severity") from exc
        _check_condition(data.get("when"), rule_id)
        return cls(rule_id, kind, severity, data["when"], str(data.get("message", "")),
                   tuple(data.get("targets", ())), tuple(data.get("disables", ())),
                   bool(data.get("requires_ack", False)), bool(data.get("enabled", True)))

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "kind": self.kind.value, "severity": self.severity.value,
                "when": self.when, "message": self.message, "targets": list(self.targets),
                "disables": list(self.disables), "requires_ack": self.requires_ack,
                "enabled": self.enabled}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    kind: RuleKind
    severity: Severity
    message: str
    targets: Tuple[str, ...] = ()
    disables: Tuple[str, ...] = ()
    requires_ack: bool = False
    capability_override: bool = False  # permanent ⚠: a capability rule was edited away


@dataclass(frozen=True)
class Diagnosis:
    findings: Tuple[Finding, ...]

    @property
    def blocking(self) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.BLOCK)

    @property
    def needs_ack(self) -> Tuple[str, ...]:
        return tuple(f.rule_id for f in self.findings if f.requires_ack)

    @property
    def capability_override(self) -> bool:
        return any(f.capability_override for f in self.findings)

    def ok_to_submit(self, acknowledged: Iterable[str] = ()) -> bool:
        return not self.blocking and set(self.needs_ack) <= set(acknowledged)

    def for_field(self, path: str) -> Tuple[Finding, ...]:
        return tuple(f for f in self.findings if path in f.targets or path in f.disables)

    def disabled_fields(self) -> Tuple[str, ...]:
        return tuple(sorted({p for f in self.findings for p in f.disables}))

    def severity_of(self, path: str) -> Optional[Severity]:
        order = [Severity.INFO, Severity.WARN, Severity.BLOCK]
        hits = [f.severity for f in self.for_field(path)]
        return max(hits, key=order.index) if hits else None


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}" if abs(value) < 1000 else f"{value:,.0f}"
    return str(value)


def render_message(template: str, ctx: Mapping[str, Any]) -> str:
    return _PLACEHOLDER.sub(lambda m: _fmt(ctx.get(m.group(1), m.group(0))), template)


def load_seed(path: Path = SEED_PATH) -> List[Rule]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = [Rule.from_dict(r) for r in data.get("rules", [])]
    ids = [r.id for r in rules]
    if len(ids) != len(set(ids)):
        raise RuleError("duplicate rule ids in seed")
    return rules


@dataclass
class RuleSet:
    """Seed rules with user edits layered on top by id."""

    seed: Sequence[Rule]
    user: Mapping[str, Rule] = field(default_factory=dict)

    def effective(self) -> List[Rule]:
        out = [self.user.get(r.id, r) for r in self.seed]
        seed_ids = {r.id for r in self.seed}
        out += [r for rid, r in self.user.items() if rid not in seed_ids]
        return out

    def evaluate(self, ctx: Mapping[str, Any], warnings_enabled: bool = True) -> Diagnosis:
        findings: List[Finding] = []
        for rule in self.effective():
            if not rule.enabled or not evaluate_condition(rule.when, ctx):
                continue
            if rule.severity is not Severity.BLOCK and rule.kind is RuleKind.POLICY and not warnings_enabled:
                continue
            findings.append(Finding(rule.id, rule.kind, rule.severity, render_message(rule.message, ctx),
                                    rule.targets, rule.disables, rule.requires_ack))
        findings += self._overrides(ctx, {f.rule_id for f in findings if f.severity is Severity.BLOCK})
        return Diagnosis(tuple(findings))

    def _overrides(self, ctx: Mapping[str, Any], still_blocking: set) -> List[Finding]:
        """A capability rule the user edited no longer blocks, but the shipped one would."""
        out = []
        for seed_rule in self.seed:
            if (seed_rule.kind is not RuleKind.CAPABILITY or seed_rule.id not in self.user
                    or seed_rule.id in still_blocking or seed_rule.severity is not Severity.BLOCK):
                continue
            if evaluate_condition(seed_rule.when, ctx):
                out.append(Finding(
                    seed_rule.id, RuleKind.CAPABILITY, Severity.WARN,
                    "⚠ Capability rule overridden: " + render_message(seed_rule.message, ctx)
                    + " The provider may reject or fail this job; that failure won't be retried.",
                    seed_rule.targets, (), requires_ack=True, capability_override=True))
        return out
