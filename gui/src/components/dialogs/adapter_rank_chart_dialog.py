"""#743/#748: adapter geometry charts — rank utilization over checkpoints,
per-layer ΔW, and the explicit ΔW-principal loss slice.

The dialog is data-driven: it receives pure `RankHistoryReport` /
`LossSliceResult` objects (backend/src/core/adapter_reports.py) computed
on worker threads, never on the GUI thread. The loss slice is an explicit
research action with the cost shown before launch and the GPU lease held
for its duration; its result is labeled a *slice along the leading ΔW
direction*, never "the loss landscape".
"""
from __future__ import annotations

from pathlib import Path

from backend.src.comfy_matrix import gpu_lease, try_admit
from backend.src.core.adapter_reports import (
    SLICE_LABEL,
    LossSliceResult,
    RankHistoryReport,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import retain_until_stopped

_EVAL_IMAGES = 4
_SLICE_LEASE_OWNER = "loss-slice"


class _Canvas:
    """Lazily-built matplotlib canvas; import kept out of module scope so
    dialog import stays light (the audit's heavy-module rule)."""

    @staticmethod
    def new(parent: QWidget):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        figure = Figure(figsize=(5.0, 3.2), dpi=100)
        canvas = FigureCanvasQTAgg(figure)
        canvas.setParent(parent)
        return canvas, figure


class LossSliceWorker(BaseQThreadWorker):
    """Runs #748's slice off the GUI thread. The lease is held by the
    dialog for the worker's whole lifetime."""

    def __init__(self, run_dir: str, checkpoint: str, record: dict, num_points: int) -> None:
        super().__init__()
        self.run_dir = run_dir
        self.checkpoint = checkpoint
        self.record = record
        self.num_points = num_points

    def _execute(self) -> object:
        error = None
        result = None
        try:
            result = self._compute()
        except Exception as exc:
            error = str(exc)
        finally:
            import gc

            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            gpu_lease.release(_SLICE_LEASE_OWNER)
        if error is not None:
            raise RuntimeError(error)
        return result

    def _compute(self) -> object:
        from backend.src.core.adapter_reports import LossSliceResult
        from backend.src.models.hooks.loss_slice import (
            build_eval_batches,
            inject_checkpoint,
            load_tuner_for_slice,
            run_diffusion_loss_slice,
        )

        config = dict(self.record.get("config") or {})
        config.setdefault("model_id", self.record.get("model_id", ""))
        config["snr_gamma"] = None
        batches = _eval_batches(self.record, count=_EVAL_IMAGES)
        if not batches:
            raise ValueError("The original dataset is unavailable; choose an accessible evaluation dataset first.")
        if not (Path(self.checkpoint).parent / "adapter_config.json").is_file():
            raise ValueError("Select a PEFT checkpoint with adapter_config.json; this adapter format is unsupported.")
        tuner = load_tuner_for_slice(config)
        inject_checkpoint(tuner, self.checkpoint)
        prepared = build_eval_batches(tuner, batches)
        result = run_diffusion_loss_slice(
            tuner,
            checkpoint_path=self.checkpoint,
            base_model=str(config.get("model_id", "")),
            eval_batches=prepared,
            num_points=self.num_points,
        )
        if not isinstance(result, LossSliceResult):
            return None
        result.to_json_file(Path(self.run_dir) / "loss_slice.json")
        return result


def _eval_batches(record: dict, count: int):
    """(pixel tensor, prompts) pairs from the run's dataset dir."""
    import torch
    from PIL import Image

    data_dir = str((record.get("config") or {}).get("data_dir") or "")
    if not data_dir or not Path(data_dir).is_dir():
        return []
    trigger = str(record.get("trigger_word") or "")
    paths = [p for p in sorted(Path(data_dir).glob("*")) if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    batches = []
    for path in paths[:count]:
        with Image.open(path) as source:
            image = source.convert("RGB").resize((512, 512))
        pixels = torch.from_numpy(_np_array(image)).permute(2, 0, 1).unsqueeze(0).float() / 127.5 - 1.0
        batches.append((pixels, [str(record.get("instance_prompt") or trigger)]))
    return batches


def _np_array(image):
    import numpy as np

    return np.asarray(image)


class AdapterRankChartDialog(QDialog):
    """Rank-utilization chart (#743) + per-layer ΔW + loss slice (#748)."""

    def __init__(
        self,
        report: RankHistoryReport,
        *,
        run_dir: str = "",
        record: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Adapter Geometry")
        self.setModal(False)
        self._report = report
        self._run_dir = run_dir
        self._record = dict(record or {})
        self._slice_worker: LossSliceWorker | None = None

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, stretch=1)

        tabs.addTab(self._utilization_tab(), "Rank Utilization")
        tabs.addTab(self._delta_tab(), "Per-Layer ΔW")
        tabs.addTab(self._slice_tab(), "Loss Slice")

        note = QLabel(SLICE_LABEL)
        note.setWordWrap(True)
        note.setStyleSheet("color: #8a8a8a;")
        root.addWidget(note)

    # -- tabs ----------------------------------------------------------------

    def _utilization_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        canvas, figure = _Canvas.new(page)
        layout.addWidget(canvas)
        axes = figure.add_subplot(111)
        snapshots = self._report.snapshots
        if not snapshots:
            axes.text(0.5, 0.5, "No adapter checkpoints found", ha="center", va="center")
        else:
            labels = [s.label for s in snapshots]
            x = range(len(snapshots))
            median = [100.0 * s.median_effective() / max(1, s.chosen_rank) for s in snapshots]
            pinned = [100.0 * s.pinned_fraction for s in snapshots]
            idle = [100.0 * s.utilization_at(0.25) for s in snapshots]
            axes.plot(x, median, marker="o", label="median eff/chosen (%)")
            axes.plot(x, pinned, marker="s", label="modules pinned at full rank (%)")
            axes.plot(x, idle, marker="^", label="modules saturated ≤ rank/4 (%)")
            axes.set_xticks(list(x))
            axes.set_xticklabels(labels, rotation=30, ha="right", fontsize=7)
            axes.set_ylabel("share of modules / utilization (%)")
            axes.legend(fontsize=7)
            axes.grid(True, alpha=0.25)
        figure.tight_layout()
        canvas.draw()
        return page

    def _delta_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self._delta_combo = QComboBox()
        for snapshot in self._report.snapshots:
            self._delta_combo.addItem(snapshot.label, snapshot.source)
        self._delta_combo.currentIndexChanged.connect(self._redraw_delta)
        layout.addWidget(self._delta_combo)
        self._delta_canvas, self._delta_figure = _Canvas.new(page)
        layout.addWidget(self._delta_canvas)
        self._redraw_delta()
        return page

    def _redraw_delta(self) -> None:
        self._delta_figure.clear()
        axes = self._delta_figure.add_subplot(111)
        index = max(0, self._delta_combo.currentIndex())
        snapshots = self._report.snapshots
        if not snapshots:
            axes.text(0.5, 0.5, "No adapter checkpoints found", ha="center", va="center")
        else:
            snapshot = snapshots[min(index, len(snapshots) - 1)]
            rows = sorted(snapshot.rows, key=lambda r: -r.fro)[:40]
            names = [r.module.split(".")[-1] or r.module for r in rows]
            axes.bar(range(len(rows)), [r.fro for r in rows])
            axes.set_xticks(range(len(rows)))
            axes.set_xticklabels(names, rotation=60, ha="right", fontsize=6)
            axes.set_ylabel("‖ΔW‖_F (top 40 layers)")
            axes.grid(True, axis="y", alpha=0.25)
        self._delta_figure.tight_layout()
        self._delta_canvas.draw()

    def _slice_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(
            "Perturbs the checkpoint's largest-‖ΔW‖ layer along its leading "
            "singular direction and measures the training loss at each α — "
            "an explicit research action, computed only on request."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self._slice_status = QLabel("Not computed for this run.")
        layout.addWidget(self._slice_status)
        self._slice_canvas_holder = QWidget()
        self._slice_canvas_holder.setLayout(QVBoxLayout(self._slice_canvas_holder))
        layout.addWidget(self._slice_canvas_holder, stretch=1)
        self._slice_result = LossSliceResult.from_json_file(Path(self._run_dir) / "loss_slice.json") if self._run_dir else None
        if self._slice_result is not None:
            self._draw_slice(self._slice_result)

        buttons = QHBoxLayout()
        self._slice_btn = QPushButton("Compute Loss Slice…")
        self._slice_btn.clicked.connect(self._on_compute_slice)
        buttons.addWidget(self._slice_btn)
        buttons.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        return page

    # -- loss slice (#748) ----------------------------------------------------

    def _on_compute_slice(self) -> None:
        if self._slice_worker is not None:
            return
        selected = self._delta_combo.currentIndex()
        latest = self._report.snapshots[selected] if 0 <= selected < len(self._report.snapshots) else self._report.latest()
        if latest is None:
            QMessageBox.information(self, "Loss Slice", "No adapter checkpoint available to slice.")
            return
        num_points = 21
        cost = (
            f"{num_points} loss evaluations over up to {_EVAL_IMAGES} eval images "
            f"(≈{num_points * _EVAL_IMAGES} forward passes, no sampling) plus one "
            "base-model load. This holds the GPU until it finishes. "
            "Uses the checkpoint selected in Per-Layer ΔW. Only PEFT adapters with a saved config are supported."
        )
        answer = QMessageBox.question(self, "Compute Loss Slice", cost + "\n\nProceed?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        refusal = try_admit(_SLICE_LEASE_OWNER)
        if refusal:
            QMessageBox.warning(self, "GPU Busy", refusal)
            return
        self._slice_status.setText(f"Computing ({num_points} points)…")
        self._slice_btn.setEnabled(False)
        worker = LossSliceWorker(self._run_dir, latest.source, self._record, num_points)
        worker.finished.connect(self._on_slice_done)
        worker.error.connect(self._on_slice_failed)
        self._slice_worker = worker
        retain_until_stopped(worker)
        worker.start()

    def _release_slice_lease(self) -> None:
        self._slice_worker = None
        self._slice_btn.setEnabled(True)

    def _on_slice_done(self, result: object) -> None:
        self._release_slice_lease()
        if not isinstance(result, LossSliceResult):
            self._slice_status.setText("Slice produced no result.")
            return
        self._slice_result = result
        self._slice_status.setText(
            f"α from -1 to 1 along the leading ΔW direction of "
            f"{result.module} (σ1={result.sigma:.3g}, {result.energy_fraction:.0%} of that layer's ΔW energy)."
        )
        self._draw_slice(result)

    def _on_slice_failed(self, exc: object) -> None:
        self._release_slice_lease()
        self._slice_status.setText(f"Slice failed: {exc}")
        QMessageBox.warning(self, "Loss Slice", f"Slice failed: {exc}")

    def _draw_slice(self, result: LossSliceResult) -> None:
        holder = self._slice_canvas_holder
        while holder.layout().count():
            item = holder.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        canvas, figure = _Canvas.new(holder)
        holder.layout().addWidget(canvas)
        axes = figure.add_subplot(111)
        axes.plot(list(result.alphas), list(result.losses), marker="o")
        axes.axvline(0.0, color="#8a8a8a", linestyle=":", label="checkpoint")
        axes.set_xlabel("α (perturbation along leading ΔW direction)")
        axes.set_ylabel("fixed-noise loss (eval subset)")
        axes.legend(fontsize=7)
        axes.grid(True, alpha=0.25)
        figure.tight_layout()
        canvas.draw()
