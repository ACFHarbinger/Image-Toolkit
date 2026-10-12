"""Training report card (#746): pure thresholds over synthetic JSONL-shaped
events — the three verdicts and the single suggestion, plus the optional
rank-utilization and duck-typed dataset-finding inputs.
"""
from types import SimpleNamespace

import pytest

from backend.src.core.training_report import (
    STATUS_BAD,
    STATUS_GOOD,
    STATUS_INFO,
    STATUS_WARN,
    RankUtilization,
    generate_training_report,
)


def _run(losses, *, steps=None, val_losses=None):
    events = []
    for i, loss in enumerate(losses):
        event = {"step": (steps[i] if steps else i + 1), "epoch": 1, "ts": 1000.0 + i, "loss": loss}
        if val_losses is not None:
            event["val_loss"] = val_losses[i]
        events.append(event)
    return events


def _finding(category, severity="warning", title="", paths=()):
    return SimpleNamespace(category=category, severity=severity, title=title, paths=tuple(paths))


# ---------------------------------------------------------------------------
# Q1: Did it learn?
# ---------------------------------------------------------------------------


def test_strong_reduction_is_green():
    card = generate_training_report(_run([1.0, 0.9, 0.7, 0.55, 0.4, 0.3, 0.22, 0.18, 0.15, 0.13]))
    learn = card.verdicts[0]
    assert learn.status == STATUS_GOOD
    assert "down" in learn.headline


def test_moderate_reduction_is_yellow():
    losses = [1.0 - i * 0.35 / 19 for i in range(20)]  # → 0.65, ~30% smoothed
    card = generate_training_report(_run(losses))
    assert card.verdicts[0].status == STATUS_WARN


def test_tiny_reduction_is_red():
    card = generate_training_report(_run([1.0, 0.99, 0.985, 0.99, 0.98, 0.985, 0.98, 0.985, 0.98, 0.982]))
    assert card.verdicts[0].status == STATUS_BAD
    assert not card.ok


def test_insufficient_data_is_info():
    card = generate_training_report(_run([0.5]))
    assert card.verdicts[0].status == STATUS_INFO
    assert card.verdicts[0].question == "Did it learn?"


def test_noise_is_smoothed_not_raw():
    # raw last value is higher than the second, but the trend is down
    card = generate_training_report(_run([1.0, 0.6, 0.62, 0.4, 0.41, 0.3, 0.31, 0.2, 0.21, 0.12]))
    assert card.verdicts[0].status == STATUS_GOOD


# ---------------------------------------------------------------------------
# Q2: Is it overfitting?
# ---------------------------------------------------------------------------


def test_val_gap_over_20_percent_warns():
    losses = [1.0 - i * 0.045 for i in range(20)]  # train → ~0.15
    vals = [1.0 - i * 0.01 for i in range(20)]     # val stalls near ~0.85
    card = generate_training_report(_run(losses, val_losses=vals))
    overfit = card.verdicts[1]
    assert overfit.status == STATUS_WARN
    assert "Train/val gap" in overfit.headline


def test_small_val_gap_is_good():
    losses = [1.0 - i * 0.04 for i in range(20)]
    card = generate_training_report(_run(losses, val_losses=[l * 1.02 for l in losses]))
    assert card.verdicts[1].status == STATUS_GOOD
    assert "Train/val gap" in card.verdicts[1].headline


def test_missing_val_and_rank_are_info():
    card = generate_training_report(_run([0.9, 0.7, 0.5, 0.4]))
    overfit = card.verdicts[1]
    assert overfit.status == STATUS_INFO
    assert "Validation loss not logged" in overfit.headline
    assert "effective-rank chart (#743)" in overfit.headline


def test_rank_utilization_healthy_band():
    card = generate_training_report(
        _run([0.9, 0.7, 0.5, 0.4]), rank_utilization=RankUtilization(14, 32),
    )
    overfit = card.verdicts[1]
    assert overfit.status == STATUS_GOOD
    assert "Rank utilization at 14/32 — healthy" in overfit.headline


def test_rank_saturated_far_below_cap_warns():
    card = generate_training_report(
        _run([0.9, 0.7, 0.5, 0.4]), rank_utilization=RankUtilization(6, 64),
    )
    assert "saturated far below the cap" in card.verdicts[1].headline
    assert card.verdicts[1].status == STATUS_WARN


def test_rank_pinned_at_cap_warns():
    card = generate_training_report(
        _run([0.9, 0.7, 0.5, 0.4]), rank_utilization=RankUtilization(31, 32),
    )
    assert "pinned at the cap" in card.verdicts[1].headline


# ---------------------------------------------------------------------------
# Q3: What to try next
# ---------------------------------------------------------------------------


def test_suggestion_prioritizes_dataset_duplicates():
    findings = [_finding("duplicates", paths=("a", "b", "c"))]
    card = generate_training_report(
        _run([1.0 - i * 0.09 for i in range(15)]), dataset_findings=findings,
    )
    assert "2 near-duplicate(s)" in card.suggestion.headline
    assert card.suggestion.status == STATUS_WARN


def test_suggestion_counts_visual_near_dup_clusters():
    findings = [_finding("diversity", title="Near-duplicate cluster: 3 visually identical images",
                         paths=("a", "b", "c"))]
    card = generate_training_report(_run([1.0, 0.9, 0.8, 0.7]), dataset_findings=findings)
    assert "near-duplicate" in card.suggestion.headline


def test_suggestion_missing_captions_second():
    findings = [_finding("captions", paths=("a", "b"))]
    card = generate_training_report(
        _run([1.0 - i * 0.09 for i in range(15)]), dataset_findings=findings,
    )
    assert "2 image(s) lack captions" in card.suggestion.headline


def test_suggestion_entanglement_mentions_tag():
    findings = [_finding("cooccurrence", title="'school_uniform' appears with trigger 'x' in 100% of 10 image(s)")]
    card = generate_training_report(_run([1.0, 0.9, 0.8, 0.7]), dataset_findings=findings)
    assert "'school_uniform' is entangled" in card.suggestion.headline


def test_suggestion_thin_clusters_when_no_bigger_issue():
    findings = [_finding("diversity", severity="info", title="2 thin cluster(s) (1, 2 images) — possibly underrepresented",
                         paths=("a", "b"))]
    card = generate_training_report(
        _run([1.0 - i * 0.09 for i in range(15)]), dataset_findings=findings,
    )
    assert "visually narrow" in card.suggestion.headline


def test_diverged_loss_suggests_lower_lr():
    card = generate_training_report(_run([0.3, 0.35, 0.5, 0.9, 1.6, 2.8, 3.5, 4.2, 4.8, 5.4]))
    assert card.suggestion.status == STATUS_BAD
    assert "lower the learning rate" in card.suggestion.headline


def test_plateau_suggests_lr_or_epochs_with_step():
    steps = list(range(100, 2100, 100))
    flat_tail = [1.0, 0.97, 0.94, 0.91, 0.88] + [0.85] * 15
    card = generate_training_report(_run(flat_tail, steps=steps))
    assert "plateaued around step" in card.suggestion.headline
    assert "higher LR or more epochs" in card.suggestion.headline


def test_rank_saturation_suggests_smaller_rank():
    card = generate_training_report(
        _run([1.0 - i * 0.09 for i in range(15)]),
        rank_utilization=RankUtilization(6, 64),
    )
    assert "try rank 9" in card.suggestion.headline


def test_clean_run_suggests_nothing_special():
    card = generate_training_report(_run([1.0 - i * 0.09 for i in range(15)]))
    assert card.suggestion.status == STATUS_GOOD
    assert card.ok


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------


def test_events_skip_garbage_and_missing_loss():
    events = [
        {"step": 1, "loss": 1.0},
        {"step": 2},                       # no loss
        "not a dict",
        {"step": 3, "loss": "oops"},
        {"step": 4, "loss": 0.5},
    ]
    card = generate_training_report(events)
    assert card.step_count == 2
    assert card.verdicts[0].status != STATUS_INFO


@pytest.mark.parametrize("events", [[], [{"step": 1, "loss": 1.0}]])
def test_degenerate_inputs_do_not_raise(events):
    card = generate_training_report(events)
    assert card.step_count == len(events)
