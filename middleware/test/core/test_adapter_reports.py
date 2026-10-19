"""#743/#748: pure report types — snapshot stats and JSON round-trips."""
import pytest

from middleware.src.core.adapter_reports import (
    SLICE_LABEL,
    CheckpointRankSnapshot,
    LossSliceResult,
    ModuleRankRow,
    RankHistoryReport,
)


def _snapshot(rows, label="epoch 0001"):
    return CheckpointRankSnapshot(label=label, source="/x", rows=tuple(rows))


def _row(module, effective, rank):
    return ModuleRankRow(module=module, effective=effective, rank=rank, max_sv=1.0, fro=1.0)


def test_median_and_chosen_rank():
    snapshot = _snapshot([_row("a", 3, 8), _row("b", 4, 8), _row("c", 16, 16)])
    assert snapshot.median_effective() == 4
    assert snapshot.chosen_rank == 16
    utilization = snapshot.utilization()
    assert utilization is not None
    assert (utilization.effective, utilization.chosen) == (4, 16)


def test_utilization_fractions():
    snapshot = _snapshot([_row("pinned", 8, 8), _row("idle", 1, 8), _row("mid", 5, 8)])
    assert snapshot.pinned_fraction == pytest.approx(1 / 3)
    # ≤ rank/4 → effective ≤ 2: "idle" counts, "mid" does not.
    assert snapshot.utilization_at(0.25) == pytest.approx(1 / 3)
    assert snapshot.utilization_at(0.75) == pytest.approx(2 / 3)


def test_empty_snapshot_degrades():
    snapshot = _snapshot([])
    assert snapshot.median_effective() == 0
    assert snapshot.chosen_rank == 0
    assert snapshot.utilization() is None
    assert snapshot.pinned_fraction == 0.0


def test_report_round_trip():
    rows = [ModuleRankRow(module="a", effective=3, rank=8, max_sv=1.5, fro=2.5)]
    report = RankHistoryReport(
        output_dir="/out",
        note="",
        snapshots=(_snapshot(rows, "epoch 0001"), _snapshot(rows, "final")),
    )
    restored = RankHistoryReport.from_dict(report.to_dict())
    assert restored == report
    assert restored.latest().label == "final"
    assert restored.latest().rows[0].utilization == pytest.approx(3 / 8)


def test_slice_result_label_is_explicit_not_landscape():
    result = LossSliceResult(
        checkpoint="/c", module="m", sigma=1.0, energy_fraction=0.5,
        alphas=(0.0,), losses=(1.0,), eval_images=2, seed=1, base_model="b",
        num_points=1,
    )
    # The label carries the disclaimer itself.
    assert "slice" in SLICE_LABEL
    assert "not the loss landscape" in SLICE_LABEL
    assert result.to_dict()["label"] == SLICE_LABEL
