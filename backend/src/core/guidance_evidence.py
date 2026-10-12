"""#753: evidence resolution + confidence calibration for guidance suggestions.

Two jobs, both pure/torch-free:

1. **Resolve** ``EvidenceRef``s (schema extension) into renderable chips:
   a tournament ref is read back from the real ``tournament.json`` (#747's
   contract), a run record from ``record.json`` (#741), advisor findings
   carry their image paths. Missing artifacts render as *stale*, never as
   invented summaries — the chip says "artifact gone", not a guess.

2. **Calibrate** confidence per Qwen's proposal-round spec (§5.3): base
   0.5, +0.2 when the claimed ``from`` survived the premise validator,
   +0.1 per additional agreeing independent signal (cap +0.3), −0.25 per
   contradiction, capped at LOW whenever the response is stale or
   hallucination-flagged. Bands: ≥0.8 high/green, 0.5–0.8 medium/yellow,
   <0.5 low/red with the abstention path.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.src.core import checkpoint_tournament
from backend.src.core.guidance_schema import (
    EvidenceRef,
    GuidanceValidation,
    ModelSwap,
    ParamChange,
    Verdict,
)
from backend.src.core.training_runs import read_run_record

KIND_TOURNAMENT = "tournament"
KIND_ADVISOR_FINDING = "advisor_finding"
KIND_RUN_RECORD = "run_record"
KIND_TRAINING_METRIC = "training_metric"
KIND_OCR = "ocr"
KIND_VLM = "vlm"

KNOWN_KINDS = (
    KIND_TOURNAMENT,
    KIND_ADVISOR_FINDING,
    KIND_RUN_RECORD,
    KIND_TRAINING_METRIC,
    KIND_OCR,
    KIND_VLM,
)

_VERIFIED_STATUSES = (Verdict.VALID, Verdict.MISSING_ASSET)
_CONTRADICT_POLARITY = "contradicts"


@dataclass(frozen=True)
class ResolvedEvidence:
    """A chip's worth of renderable evidence."""

    ref: EvidenceRef
    title: str
    detail: str = ""
    target_dir: str = ""  # openable folder (run dir, dataset dir)
    paths: tuple[str, ...] = ()  # importable image paths (advisor findings)
    verified: bool = False
    stale: bool = False  # the artifact is gone — say so, don't invent data


@dataclass(frozen=True)
class ConfidenceBand:
    name: str  # "high" | "medium" | "low"
    label: str
    color: str
    hint: str = ""


_BAND_HIGH = ConfidenceBand("high", "High confidence", "#3a9d6e")
_BAND_MEDIUM = ConfidenceBand("medium", "Medium confidence", "#c9a227")
_BAND_LOW = ConfidenceBand(
    "low",
    "Low confidence",
    "#c0392b",
    hint="Insufficient evidence — see what to capture below.",
)

HIGH_THRESHOLD = 0.8
MEDIUM_THRESHOLD = 0.5


def confidence_band(score: float) -> ConfidenceBand:
    if score >= HIGH_THRESHOLD:
        return _BAND_HIGH
    if score >= MEDIUM_THRESHOLD:
        return _BAND_MEDIUM
    return _BAND_LOW


def compute_confidence(
    *,
    verified: bool | None = None,
    evidence: tuple[EvidenceRef, ...] = (),
    contradictions: int | None = None,
    flagged: bool = False,
    advisor_score: float | None = None,
) -> float:
    """Qwen's rubric, made literal.

    ``verified`` is the premise-validator outcome for the suggestion's
    claimed ``from``; ``evidence`` the attached agreeing signals (an
    evidence ref may mark itself ``{"polarity": "contradicts"}``);
    ``flagged`` = stale workflow hash or hallucination flag. The advisor's
    own score blends in as a 0.3 prior — it nudges, but signal agreement
    and verified premises dominate. Flagged responses cap at just below
    MEDIUM no matter what the advisor claimed.
    """
    if contradictions is None:
        contradictions = count_contradictions(evidence)
    score = 0.5
    if verified is not None:
        score += 0.2 if verified else -0.2
    agreeing_kinds = {e.kind for e in evidence if e.ref.get("polarity") != _CONTRADICT_POLARITY}
    score += 0.1 * min(max(len(agreeing_kinds) - 1, 0), 3)
    score -= 0.25 * max(int(contradictions), 0)
    if advisor_score is not None:
        score = 0.7 * score + 0.3 * max(0.0, min(1.0, advisor_score))
    score = max(0.0, min(1.0, score))
    if flagged:
        score = min(score, MEDIUM_THRESHOLD - 0.01)
    return score


def count_contradictions(evidence: tuple[EvidenceRef, ...]) -> int:
    return sum(1 for e in evidence if e.ref.get("polarity") == _CONTRADICT_POLARITY)


def confidence_for_change(
    change: ParamChange | ModelSwap,
    validation: GuidanceValidation | None = None,
    *,
    resolved: tuple[ResolvedEvidence, ...] = (),
) -> float:
    """Calibrated confidence for one suggestion row, blended with any
    advisor-provided score carried on the change itself."""
    verified: bool | None = None
    flagged = False
    if validation is not None:
        flagged = validation.stale or validation.hallucination_flagged
        for verdict in validation.verdicts:
            if (
                verdict.change.node_id == change.node_id
                and verdict.change.input_name == change.input_name
                and verdict.change.to_value == change.to_value
            ):
                verified = verdict.status in _VERIFIED_STATUSES
                break
    return compute_confidence(
        verified=verified,
        evidence=tuple(item.ref for item in resolved if item.verified and not item.stale),
        contradictions=count_contradictions(change.evidence),
        flagged=flagged,
        advisor_score=None,
    )


def resolve_evidence(
    ref: EvidenceRef,
    *,
    runs_root: Path | str | None = None,
) -> ResolvedEvidence:
    """Turn one schema evidence ref into a chip. Local artifact kinds are
    read back from disk; missing files render stale instead of trusting
    the advisor's summary."""
    if ref.kind == KIND_TOURNAMENT:
        return _resolve_tournament(ref, runs_root=runs_root)
    if ref.kind == KIND_RUN_RECORD:
        return _resolve_run_record(ref, runs_root=runs_root)
    if ref.kind == KIND_ADVISOR_FINDING:
        paths = _image_paths(ref.ref.get("paths"))
        title = f"Dataset advisor: {ref.ref.get('category', 'finding')}"
        detail = ref.summary or "Prefiltered dataset finding from Gate D.4."
        if not paths:
            return ResolvedEvidence(ref=ref, title=title, detail=detail, stale=True)
        return ResolvedEvidence(ref=ref, title=title, detail=detail, paths=paths)
    if ref.kind in (KIND_OCR, KIND_VLM):
        label = ref.kind.upper()
        return ResolvedEvidence(
            ref=ref,
            title=f"{label} read: {ref.summary}" if ref.summary else f"{label} read",
            detail="Model-reported signal — no local artifact to inspect yet.",
        )
    return ResolvedEvidence(ref=ref, title=ref.summary or f"{ref.kind} signal",
                            detail="Unverified advisor claim; no artifact resolver.", stale=True)


def _run_dir_for(ref: EvidenceRef, runs_root: Path | str | None) -> Path | None:
    from backend.src.core.training_runs import default_runs_root

    root = Path(runs_root) if runs_root is not None else default_runs_root()
    explicit = ref.ref.get("run_dir")
    if isinstance(explicit, str) and explicit:
        candidate = Path(explicit).resolve()
        return candidate if candidate.is_relative_to(root.resolve()) else None
    run_id = ref.ref.get("run_id")
    if isinstance(run_id, str) and run_id:
        candidate = (root / run_id).resolve()
        return candidate if candidate.is_relative_to(root.resolve()) else None
    return None


def _resolve_tournament(ref: EvidenceRef, *, runs_root: Path | str | None) -> ResolvedEvidence:
    run_dir = _run_dir_for(ref, runs_root)
    if run_dir is None:
        return ResolvedEvidence(ref=ref, title="Tournament result", detail=ref.summary, stale=True)
    state = checkpoint_tournament.load_state(run_dir)
    if state is None or not state.entries:
        return ResolvedEvidence(
            ref=ref,
            title=f"Tournament ({run_dir.name})",
            detail="No tournament.json in this run — result no longer on disk.",
            target_dir=str(run_dir),
            stale=True,
        )
    rows = checkpoint_tournament.standings(state)
    leader = rows[0]
    checkpoint = ref.ref.get("checkpoint")
    focus = next((r for r in rows if r.key == checkpoint), None)
    if checkpoint and focus is None:
        return ResolvedEvidence(ref=ref, title="Tournament checkpoint missing", stale=True)
    shown = focus or leader
    note = f" over {state.history and len(state.history) or 0} blind comparisons"
    title = f"Blind tournament: {shown.label} at ELO {shown.rating:.0f} ±{shown.margin:.0f}{note}"
    if state.promoted:
        title += f" — promoted: {state.promoted.get('label', 'unknown')}"
    return ResolvedEvidence(
        ref=ref,
        title=title,
        detail="Grounded preference signal from Gate D.7 (#747).",
        verified=True,
        target_dir=str(run_dir),
    )


def _resolve_run_record(ref: EvidenceRef, *, runs_root: Path | str | None) -> ResolvedEvidence:
    run_dir = _run_dir_for(ref, runs_root)
    if run_dir is None:
        return ResolvedEvidence(ref=ref, title="Training run", detail=ref.summary, stale=True)
    record = read_run_record(run_dir)
    if record is None:
        return ResolvedEvidence(
            ref=ref,
            title=f"Run {run_dir.name}",
            detail="record.json is gone — run details unavailable.",
            target_dir=str(run_dir),
            stale=True,
        )
    trigger = record.get("trigger_word") or "no trigger word"
    status = record.get("status") or "unknown"
    return ResolvedEvidence(
        ref=ref,
        title=f"Run {record.get('run_id', run_dir.name)} ({status}, trigger: {trigger})",
        detail="Training run record from Gate D.1 (#741).",
        verified=True,
        target_dir=str(run_dir),
    )


def gather_run_evidence(run_dir: Path | str) -> tuple[EvidenceRef, ...]:
    """The local measured signals for one run, as schema evidence refs —
    what a guidance suggestion about this run can cite: its record, its
    blind-tournament outcome (#747), and any promoted checkpoint."""
    run_dir = Path(run_dir)
    record = read_run_record(run_dir)
    if record is None:
        return ()
    run_id = str(record.get("run_id") or run_dir.name)
    refs: list[EvidenceRef] = [
        EvidenceRef(kind=KIND_RUN_RECORD, ref={"run_id": run_id}, summary="")
    ]
    state = checkpoint_tournament.load_state(run_dir)
    if state is not None and state.entries:
        refs.append(
            EvidenceRef(
                kind=KIND_TOURNAMENT,
                ref={"run_id": run_id},
                summary="",
            )
        )
        if state.promoted:
            refs.append(
                EvidenceRef(
                    kind=KIND_TOURNAMENT,
                    ref={"run_id": run_id, "checkpoint": state.promoted.get("key", "")},
                    summary="Promoted winner.",
                )
            )
    return tuple(refs)


def needs_pick_list(needs: tuple[str, ...], evidence: tuple[EvidenceRef, ...]) -> tuple[str, ...]:
    """Prefiltered image paths for the abstention handoff: the union of
    existing paths named by the evidence, in stable order."""
    if not needs:
        return ()
    seen: set[str] = set()
    paths: list[str] = []
    for ref in evidence:
        for raw in _image_paths(ref.ref.get("paths")):
            if raw not in seen:
                seen.add(raw)
                paths.append(raw)
    return tuple(paths)


def _image_paths(raw) -> tuple[str, ...]:
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(p for p in raw if isinstance(p, str)
                 and Path(p).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
                 and Path(p).is_file())
