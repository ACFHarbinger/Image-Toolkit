"""#743/#748 GUI: rank chart dialog, report-card hook, loss-slice gating.

The backend geometry is mocked away by the GUI conftest's models tree —
these tests assert the wiring, the mock degradation path, and the
explicit gating of the slice, using real pure-type data
(middleware/src/core/adapter_reports.py is torch-free and importable).
"""
import time
from unittest.mock import patch

import pytest
from gui.src.components.dialogs.adapter_rank_chart_dialog import (
    _SLICE_LEASE_OWNER,
    AdapterRankChartDialog,
)
from gui.src.components.dialogs.training_report_card_dialog import TrainingReportCardDialog
from middleware.src.comfy_matrix import gpu_lease
from middleware.src.core.adapter_reports import (
    CheckpointRankSnapshot,
    LossSliceResult,
    ModuleRankRow,
    RankHistoryReport,
)
from middleware.src.core.training_report import STATUS_GOOD, ReportCard, ReportVerdict
from middleware.src.core.training_runs import start_run
from PySide6.QtTest import QTest as qt_test
from PySide6.QtWidgets import QPushButton, QTabWidget

pytestmark = pytest.mark.gui


def _report():
    rows = (
        ModuleRankRow(module="unet.big", effective=3, rank=8, max_sv=1.5, fro=2.5),
        ModuleRankRow(module="unet.small", effective=8, rank=8, max_sv=0.5, fro=0.2),
    )
    return RankHistoryReport(
        output_dir="/out",
        snapshots=(
            CheckpointRankSnapshot(label="epoch 0001", source="/out/ckpt1", rows=rows),
            CheckpointRankSnapshot(label="final", source="/out/final", rows=rows),
        ),
    )


def _card():
    verdict = ReportVerdict(question="Did it learn?", status=STATUS_GOOD, headline="Loss fell")
    return ReportCard(verdicts=(verdict,), suggestion=verdict, step_count=10)


def _wait_until(predicate, timeout=4.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qt_test.qWait(20)
        if predicate():
            return True
    return False


@pytest.fixture(autouse=True)
def _clean_lease():
    yield
    gpu_lease.release(_SLICE_LEASE_OWNER)


def test_dialog_renders_three_tabs(q_app):
    dialog = AdapterRankChartDialog(_report(), run_dir="/tmp/run", record={})
    tab_widget = dialog.findChild(QTabWidget)
    assert tab_widget is not None
    assert tab_widget.count() == 3
    dialog.close()


def test_report_card_rank_button_gated(q_app):
    without = TrainingReportCardDialog(_card(), run_dir="/tmp/r")
    assert all(b.text() != "View Rank Chart" for b in without.findChildren(QPushButton))
    with_button = TrainingReportCardDialog(_card(), run_dir="/tmp/r", rank_chart_available=True)
    rank_btn = next(b for b in with_button.findChildren(QPushButton) if b.text() == "View Rank Chart")
    received = []
    with_button.rank_chart_requested.connect(lambda: received.append(True))
    rank_btn.click()
    assert received == [True]


def test_rank_utilization_degrades_under_model_mocks(tmp_path):
    """In the GUI test process adapter_geometry is a MagicMock: the helper
    must degrade to (None, True) — never feed fakes into the card."""
    from gui.src.tabs.models.delta.lora_train_tab import _rank_utilization_for_run

    run_dir = start_run(
        runs_root=tmp_path / "runs", run_id="r1", output_name="out",
        engine="locon", model_id="m",
        lora_path=str(tmp_path / "out" / "lora_weights.safetensors"),
    )
    utilization, available = _rank_utilization_for_run(str(run_dir))
    assert utilization is None
    assert available is True


def test_rank_utilization_absent_without_artifacts(tmp_path):
    from gui.src.tabs.models.delta.lora_train_tab import _rank_utilization_for_run

    run_dir = start_run(
        runs_root=tmp_path / "runs", run_id="r2", output_name="out",
        engine="standard", model_id="m",  # no lora_path
    )
    utilization, available = _rank_utilization_for_run(str(run_dir))
    assert utilization is None
    assert available is False


def test_slice_button_requires_confirmation(q_app, tmp_path):
    dialog = AdapterRankChartDialog(_report(), run_dir=str(tmp_path), record={})
    with patch("gui.src.components.dialogs.adapter_rank_chart_dialog.QMessageBox") as msg:
        msg.question.return_value = msg.StandardButton.No
        dialog._on_compute_slice()
        msg.question.assert_called_once()
    assert dialog._slice_worker is None
    assert gpu_lease.owner is None


def test_slice_lease_held_through_run_and_released(q_app, tmp_path):
    from gui.src.components.dialogs.adapter_rank_chart_dialog import LossSliceWorker

    class _StubWorker(LossSliceWorker):
        def __init__(self, run_dir, checkpoint, record, num_points):
            super().__init__(run_dir, checkpoint, record, num_points)

        def _compute(self) -> object:
            return None  # degrades to "no result" without touching diffusers

    dialog = AdapterRankChartDialog(_report(), run_dir=str(tmp_path), record={})
    with patch("gui.src.components.dialogs.adapter_rank_chart_dialog.QMessageBox") as msg, \
         patch("gui.src.components.dialogs.adapter_rank_chart_dialog.LossSliceWorker", _StubWorker):
        msg.question.return_value = msg.StandardButton.Yes
        dialog._on_compute_slice()
        assert gpu_lease.owner == _SLICE_LEASE_OWNER
        assert _wait_until(lambda: dialog._slice_worker is None)
        assert dialog._slice_btn.isEnabled()
        assert gpu_lease.owner is None
        assert "no result" in dialog._slice_status.text().lower()

    result = LossSliceResult(
        checkpoint="/final", module="unet.big", sigma=1.5, energy_fraction=0.9,
        alphas=(-1.0, 0.0, 1.0), losses=(1.2, 1.0, 1.1),
        eval_images=4, seed=42, base_model="m", num_points=3,
    )
    dialog._on_slice_done(result)
    assert "unet.big" in dialog._slice_status.text()
    assert gpu_lease.owner is None
