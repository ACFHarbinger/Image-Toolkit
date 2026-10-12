"""Training report card (#746): the three-question summary every user has
after a run, computed by a pure function over the #741 JSONL event log —
no model calls, just threshold checks (Qwen's proposal §4.2).

1. Did it learn? — smoothed loss delta start→end (green >50%, yellow
   20–50%, red <20%).
2. Is it overfitting? — train/val gap when validation loss is logged,
   effective-rank utilization when Gate D.3 (#743) supplies it; both
   halves are conditional, matching the issue's "when validation is
   wired" wording.
3. What to try next — the single highest-impact suggestion, dataset
   hygiene first, then rank, then LR/epochs.

`dataset_findings` is duck-typed (objects with category/severity/title/
paths attributes — Kimi's `AdvisorFinding` from #744 qualifies), so this
module has no dependency on when #744 merges.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

STATUS_GOOD = "good"
STATUS_WARN = "warn"
STATUS_BAD = "bad"
STATUS_INFO = "info"

LEARN_GREEN = 0.50
LEARN_YELLOW = 0.20
VAL_GAP_WARN = 0.20
PLATEAU_MIN_STEPS = 10
PLATEAU_REL_IMPROVEMENT = 0.02
_SMOOTH_ALPHA = 0.25
_TAIL_FRAC = 0.2


@dataclass(frozen=True)
class RankUtilization:
    """Effective vs chosen adapter rank, computed by Gate D.3 (#743)."""

    effective: int
    chosen: int


@dataclass(frozen=True)
class ReportVerdict:
    question: str
    status: str  # STATUS_GOOD | STATUS_WARN | STATUS_BAD | STATUS_INFO
    headline: str
    detail: str = ""


@dataclass(frozen=True)
class ReportCard:
    verdicts: tuple[ReportVerdict, ...]
    suggestion: ReportVerdict
    step_count: int

    @property
    def ok(self) -> bool:
        return all(v.status != STATUS_BAD for v in self.verdicts)


def _extract_series(events: Iterable[dict]) -> tuple[list[int], list[float], list[float], int]:
    steps: list[int] = []
    losses: list[float] = []
    val_losses: list[float] = []
    nonfinite = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        loss = event.get("loss")
        if loss is None:
            continue
        try:
            value = float(loss)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            nonfinite += 1
            continue
        try:
            step = int(event.get("step", len(steps)))
        except (TypeError, ValueError, OverflowError):
            continue
        steps.append(step)
        losses.append(value)
        val = event.get("val_loss", event.get("validation_loss"))
        try:
            val_losses.append(float(val))
        except (TypeError, ValueError):
            val_losses.append(float("nan"))
    return steps, losses, val_losses, nonfinite


def _smooth(values: Sequence[float], alpha: float = _SMOOTH_ALPHA) -> list[float]:
    smoothed = [values[0]]
    for value in values[1:]:
        smoothed.append(alpha * value + (1 - alpha) * smoothed[-1])
    return smoothed


def _tail_head(values: Sequence[float]) -> tuple[float, float]:
    """(head mean, tail mean) over the first/last ~20% of the series."""
    window = max(1, int(len(values) * 0.2))
    head = sum(values[:window]) / window
    tail_values = values[-window:]
    tail = sum(tail_values) / len(tail_values)
    return head, tail


def _fmt_pct(fraction: float) -> str:
    return f"{fraction * 100:.0f}%"


def _learn_verdict(losses: Sequence[float]) -> ReportVerdict:
    question = "Did it learn?"
    if len(losses) < 2:
        return ReportVerdict(question, STATUS_INFO, "Not enough data",
                             "Fewer than two logged loss values")
    head, tail = _tail_head(_smooth(losses))
    reduction = (head - tail) / head if head > 1e-12 else 0.0
    headline = f"Loss {_fmt_pct(abs(reduction))} {'down' if reduction >= 0 else 'up'} " \
               f"({head:.3g} → {tail:.3g})"
    if reduction >= LEARN_GREEN:
        return ReportVerdict(question, STATUS_GOOD, headline,
                             f"Over {len(losses)} logged steps")
    if reduction >= LEARN_YELLOW:
        return ReportVerdict(question, STATUS_WARN, headline,
                             "Progressing, but slowly — see suggestions")
    return ReportVerdict(question, STATUS_BAD, headline,
                         "The run barely moved the loss")


def _overfit_verdict(
    losses: Sequence[float], val_losses: Sequence[float],
    rank: RankUtilization | None,
) -> ReportVerdict:
    question = "Is it overfitting?"
    parts: list[tuple[str, str, str]] = []  # (status, headline, detail)

    pairs = [(train, val) for train, val in zip(losses, val_losses, strict=True)
             if math.isfinite(val)]
    usable_vals = [val for _, val in pairs]
    if len(usable_vals) >= 2:
        _, tail_train = _tail_head([train for train, _ in pairs])
        val_window = max(1, int(len(usable_vals) * 0.2))
        tail_val = sum(usable_vals[-val_window:]) / val_window
        if tail_train > 1e-12:
            # Overfitting = validation pulling away from training.
            gap = (tail_val - tail_train) / tail_train
            if gap > VAL_GAP_WARN:
                parts.append((STATUS_WARN,
                              f"Train/val gap {_fmt_pct(gap)}",
                              "Validation loss is pulling away from training — the model may be memorizing"))
            else:
                parts.append((STATUS_GOOD, f"Train/val gap {_fmt_pct(max(gap, 0.0))}", ""))
        else:
            parts.append((STATUS_INFO, "Train/val gap unavailable", ""))
    else:
        parts.append((STATUS_INFO, "Validation loss not logged", ""))

    if rank is not None and rank.chosen > 0:
        ratio = rank.effective / rank.chosen
        headline = f"Rank utilization at {rank.effective}/{rank.chosen}"
        if ratio < 0.3:
            parts.append((STATUS_WARN, headline + " — saturated far below the cap",
                          "The adapter is over-parameterized — a smaller rank saves VRAM and file size"))
        elif ratio >= 0.95:
            parts.append((STATUS_WARN, headline + " — pinned at the cap",
                          "Rank may be the bottleneck while loss still falls"))
        else:
            parts.append((STATUS_GOOD, headline + " — healthy", ""))
    else:
        parts.append((STATUS_INFO, "Rank utilization — available with the effective-rank chart (#743)", ""))

    order = {STATUS_BAD: 0, STATUS_WARN: 1, STATUS_INFO: 2, STATUS_GOOD: 3}
    parts.sort(key=lambda p: order[p[0]])
    if any(p[0] == STATUS_BAD for p in parts):
        status = STATUS_BAD
    elif any(p[0] == STATUS_WARN for p in parts):
        status = STATUS_WARN
    elif any(p[0] == STATUS_GOOD for p in parts):
        # An unavailable half-signal must not dilute an available good one.
        status = STATUS_GOOD
    else:
        status = STATUS_INFO
    headline = "; ".join(p[1] for p in parts)
    detail = next((p[2] for p in parts if p[2]), "")
    return ReportVerdict(question, status, headline, detail)


def _suggestion(
    losses: Sequence[float], steps: Sequence[int], rank: RankUtilization | None,
    dataset_findings: Sequence[Any],
) -> ReportVerdict:
    question = "What to try next"

    def findings(category: str):
        return [f for f in dataset_findings if getattr(f, "category", None) == category]

    dup_extra = sum(
        max(len(getattr(f, "paths", ()) or ()) - 1, 1)
        for f in findings("duplicates") + [
            f for f in findings("diversity")
            if str(getattr(f, "title", "")).startswith("Near-duplicate cluster")
        ]
    )
    if dup_extra:
        return ReportVerdict(question, STATUS_WARN,
                             f"Dataset has {dup_extra} near-duplicate(s) — remove them",
                             "Exact or visual duplicates teach nothing new; the advisor can exclude them")
    missing = [f for f in findings("captions") if getattr(f, "severity", None) == "warning"]
    if missing:
        count = sum(len(getattr(f, "paths", ()) or ()) for f in missing)
        return ReportVerdict(question, STATUS_WARN,
                             f"{count} image(s) lack captions — caption them (WD14) before retraining",
                             "Uncaptioned images train the trigger without decoupled concepts")
    entangled = [f for f in findings("cooccurrence") if getattr(f, "severity", None) == "warning"]
    if entangled:
        title = str(getattr(entangled[0], "title", ""))
        tag = title.split("'")[1] if "'" in title else "a tag"
        return ReportVerdict(question, STATUS_WARN,
                             f"'{tag}' is entangled with the trigger — add regularization images",
                             "The concept always appears with the character, so it leaks into the trigger")
    narrow = [f for f in findings("diversity") if "thin cluster" in str(getattr(f, "title", ""))]
    if narrow:
        return ReportVerdict(question, STATUS_WARN,
                             "The dataset is visually narrow — add pose/angle/background variety",
                             "Thin clusters hint at underrepresented views")

    if len(losses) >= 2:
        smoothed = _smooth(losses)
        head, tail = _tail_head(smoothed)
        if tail > head and head > 1e-12:
            return ReportVerdict(question, STATUS_BAD,
                                 f"Loss went up {_fmt_pct((tail - head) / head)} — lower the learning rate",
                                 "Diverged runs rarely recover; LR 3–10× lower is the usual fix")
        if len(losses) >= PLATEAU_MIN_STEPS:
            tail_window = max(2, int(len(smoothed) * _TAIL_FRAC))
            previous = smoothed[-2 * tail_window:-tail_window]
            recent = smoothed[-tail_window:]
            if previous:
                prev_mean = sum(previous) / len(previous)
                recent_mean = sum(recent) / len(recent)
                if prev_mean > 1e-12 and (prev_mean - recent_mean) / prev_mean < PLATEAU_REL_IMPROVEMENT:
                    plateau_step = steps[int(0.8 * (len(steps) - 1))] if steps else len(losses)
                    return ReportVerdict(question, STATUS_WARN,
                                         f"Loss plateaued around step {plateau_step} — try higher LR or more epochs",
                                         "The smoothed curve flattened over the last fifth of the run")

    if rank is not None and rank.chosen > 0:
        ratio = rank.effective / rank.chosen
        if ratio < 0.3:
            return ReportVerdict(question, STATUS_WARN,
                                 f"Effective rank saturated at {rank.effective}/{rank.chosen} — "
                                 f"try rank {max(1, int(round(rank.effective * 1.5)))}",
                                 "The adapter barely uses its budget — a smaller rank is cheaper and as good")
        if ratio >= 0.95:
            return ReportVerdict(question, STATUS_WARN,
                                 f"Effective rank pinned at {rank.chosen}/{rank.chosen} — try a higher rank",
                                 "The adapter wants more degrees of freedom than it has")

    return ReportVerdict(question, STATUS_GOOD,
                         "Nothing stands out — vary the data or compare checkpoints in a tournament (#747)",
                         "")


def generate_training_report(
    events: Iterable[dict],
    *,
    rank_utilization: RankUtilization | None = None,
    dataset_findings: Sequence[Any] = (),
) -> ReportCard:
    """Build the three-question card from a run's JSONL events (#746).

    Pure: no I/O, no model, safe on the GUI thread. `dataset_findings` is
    duck-typed (AdvisorFinding-shaped) so both #744 merge orders work.
    """
    steps, losses, val_losses, nonfinite = _extract_series(events)
    learn = _learn_verdict(losses)
    overfit = _overfit_verdict(losses, val_losses, rank_utilization)
    suggestion = _suggestion(losses, steps, rank_utilization, dataset_findings)
    if nonfinite:
        learn = ReportVerdict("Did it learn?", STATUS_BAD, "Non-finite loss recorded",
                              f"{nonfinite} logged loss value(s) were NaN or infinity")
        suggestion = ReportVerdict("What to try next", STATUS_BAD,
                                   "Check numerical stability before using these weights")
    return ReportCard(
        verdicts=(learn, overfit),
        suggestion=suggestion,
        step_count=len(losses) + nonfinite,
    )
