"""Preflight in a fixed order, shared by the UI and the backend submit path (#831).

validate → data class → secret scan → weight classes → quota probe → cost →
risk rules → Plan & cost sheet. Every stage runs (except after a validation
error) so the user sees all problems at once, not one per submit.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from ..adapter import CapabilityManifest, QuotaExceeded
from ..cost.catalogue import PriceCatalogue
from ..cost.estimate import Estimate, estimate
from ..risk.context import build_context
from ..risk.engine import Diagnosis, RuleSet, Severity, load_seed
from ..settings import CloudSettings
from ..spec import JobSpec, SpecError
from .scans import SecretFinding, WeightClass, classify_weights, redact_workflow, scan_workflow_secrets

STAGES = ("validate", "data_class", "secrets", "weights", "quota", "cost", "risk")

KEEP = "keep"
STRIP = "strip"


@dataclass(frozen=True)
class Issue:
    stage: str
    severity: Severity
    message: str
    ack_id: Optional[str] = None  # set when the user may acknowledge instead of fixing
    targets: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PreflightReport:
    spec: JobSpec  # with stripped secrets removed; this is what gets submitted
    issues: Tuple[Issue, ...]
    estimate: Estimate
    diagnosis: Diagnosis
    secret_findings: Tuple[SecretFinding, ...] = ()
    redacted_workflow: Optional[Dict[str, Any]] = None
    excluded_weights: Tuple[str, ...] = ()
    stages_run: Tuple[str, ...] = ()

    @property
    def blocking(self) -> Tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity is Severity.BLOCK and i.ack_id is None)

    @property
    def needs_ack(self) -> Tuple[str, ...]:
        return tuple(i.ack_id for i in self.issues if i.ack_id is not None)

    def ok_to_submit(self, acknowledged: Iterable[str] = ()) -> bool:
        return not self.blocking and set(self.needs_ack) <= set(acknowledged)

    @property
    def capability_override(self) -> bool:
        return self.diagnosis.capability_override

    def sheet(self) -> Dict[str, Any]:
        """The Plan & cost confirmation sheet; Submit is a separate, explicit click."""
        pl = self.spec.placement
        return {
            "job_id": self.spec.job_id,
            "kind": self.spec.kind.value,
            "provider": pl.provider,
            "region": pl.region,
            "mode": pl.mode.value,
            "storage": self.spec.storage.value,
            "data_class": self.spec.data_class.value,
            "shards": len(self.spec.shards),
            "staging_bytes": sum(b.size_bytes for b in self.spec.inputs.values()),
            "estimate_known": self.estimate.known,
            "estimate": self.estimate.breakdown(),
            "price_age_days": self.estimate.price_age_days,
            "issues": [{"stage": i.stage, "severity": i.severity.value, "message": i.message,
                        "ack_id": i.ack_id, "targets": list(i.targets)} for i in self.issues],
            "needs_ack": list(self.needs_ack),
            "capability_override": self.capability_override,
        }


def run_preflight(
    spec: JobSpec,
    *,
    catalogue: PriceCatalogue,
    settings: CloudSettings,
    manifest: Optional[CapabilityManifest] = None,
    adapter: Any = None,
    ruleset: Optional[RuleSet] = None,
    month_to_date_usd: float = 0.0,
    weight_classes: Mapping[str, WeightClass] = None,
    secret_decisions: Mapping[Tuple[str, str], str] = None,
    watchdog_configured: bool = False,
    today: Optional[_dt.date] = None,
) -> PreflightReport:
    issues: List[Issue] = []
    ran: List[str] = []
    empty = Diagnosis(())

    ran.append("validate")
    try:
        spec.validate()
    except SpecError as exc:
        issues.append(Issue("validate", Severity.BLOCK, str(exc)))
        return PreflightReport(spec, tuple(issues), Estimate(False), empty, stages_run=tuple(ran))

    ran.append("data_class")
    if manifest is None and adapter is not None:
        manifest = adapter.capabilities()

    ran.append("secrets")
    spec, secret_hits, redacted = _secrets(spec, secret_decisions or {}, issues)

    ran.append("weights")
    spec, excluded = _weights(spec, weight_classes or {}, issues)

    ran.append("quota")
    probe = getattr(adapter, "probe_quota", None)
    if callable(probe):
        try:
            probe(spec)
        except QuotaExceeded as exc:
            link = f" Request more: {exc.request_url}" if exc.request_url else ""
            issues.append(Issue("quota", Severity.BLOCK, f"{exc}.{link}", targets=("placement.provider",)))

    ran.append("cost")
    est = estimate(spec, catalogue, today=today) if settings.estimates_enabled else Estimate(False)

    ran.append("risk")
    ctx = build_context(spec, manifest, est, settings, month_to_date_usd, watchdog_configured)
    diag = (ruleset or RuleSet(load_seed())).evaluate(ctx, settings.warnings_enabled)
    for f in diag.findings:
        ack = f.rule_id if f.requires_ack else None
        issues.append(Issue("risk", f.severity, f.message, ack if f.severity is not Severity.BLOCK else None,
                            f.targets))
    return PreflightReport(spec, tuple(issues), est, diag, tuple(secret_hits), redacted, tuple(excluded),
                           tuple(ran))


def _secrets(spec: JobSpec, decisions: Mapping[Tuple[str, str], str],
             issues: List[Issue]) -> Tuple[JobSpec, List[SecretFinding], Optional[Dict[str, Any]]]:
    workflow = spec.params.get("workflow")
    if not isinstance(workflow, Mapping):
        return spec, [], None
    hits = scan_workflow_secrets(workflow)
    if not hits:
        return spec, [], dict(workflow)
    strip = [h for h in hits if decisions.get((h.node_id, h.field)) == STRIP]
    for h in hits:
        choice = decisions.get((h.node_id, h.field))
        if choice not in (KEEP, STRIP):
            issues.append(Issue("secrets", Severity.BLOCK,
                                f"Node {h.node_id} field {h.field!r} looks like a secret ({h.reason}). "
                                "Strip it or explicitly keep it.", targets=(f"workflow.{h.node_id}",)))
        elif choice == KEEP:
            issues.append(Issue("secrets", Severity.WARN,
                                f"Node {h.node_id} field {h.field!r} will be uploaded as-is ({h.reason}).",
                                targets=(f"workflow.{h.node_id}",)))
    if strip:
        spec = replace(spec, params={**spec.params, "workflow": redact_workflow(workflow, strip, "")})
    return spec, hits, redact_workflow(workflow, hits)


def _weights(spec: JobSpec, classes: Mapping[str, WeightClass],
             issues: List[Issue]) -> Tuple[JobSpec, List[str]]:
    weights: Mapping[str, str] = spec.params.get("weights") or {}
    if not weights:
        return spec, []
    excluded: List[str] = []
    for v in classify_weights(weights, classes):
        if v.cls is WeightClass.BLOCK:
            excluded.append(v.sha256)
            issues.append(Issue("weights", Severity.BLOCK,
                                f"{v.name} is classed `block` and never leaves this machine; "
                                "remove it from the job or reclassify it.", targets=("weights",)))
        elif v.cls is WeightClass.WARN:
            why = "has no cloud class yet" if not v.known else "is classed `warn`"
            issues.append(Issue("weights", Severity.WARN, f"{v.name} {why}; it will be uploaded.",
                                ack_id=f"weight:{v.sha256}", targets=("weights",)))
    if excluded:
        inputs = {k: b for k, b in spec.inputs.items() if k not in excluded}
        shards = tuple(replace(s, inputs=tuple(i for i in s.inputs if i not in excluded)) for s in spec.shards)
        spec = replace(spec, inputs=inputs, shards=shards)
    return spec, excluded


def required_acks(report: PreflightReport) -> Set[str]:
    return set(report.needs_ack)


__all__: Sequence[str] = ("KEEP", "STRIP", "Issue", "PreflightReport", "run_preflight", "required_acks", "STAGES")
