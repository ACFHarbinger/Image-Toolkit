"""InspectorWindow: the top-level PySide6 window for per-test evaluation.

Assembles the queue sidebar, the N-way panel grid, the tool tabs
(visualisations / comparison / diagnostics / metrics / artifacts), the scoring
form, and the annotation flow, over an ``EvaluationSession`` that owns queue and
persistence semantics.

``RatingDashboard`` remains as an alias so ``bench_eval_dispatch.py`` and any
existing smoke test keep constructing "the window" by its old name.

Keyboard-first by design — §0.1 budgets ~28 s per test, which a mouse-only form
can't reach. The key map lives in ``shortcuts.py`` and the annotation flow in
``annotation_flow.py``, both split out to keep this file within the repo's
500-LoC budget (§5.17 / issues #121-#122); the user-facing crib sheet is
``KEY_HINTS`` in ``constants/user_interface.py``, rendered into the window footer.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..constants.schema import (
    COMPARATOR_TITLES,
    DEFECTS,
)
from ..constants.user_interface import (
    COL_TEXT_DIM,
    DISPLAY_PIXEL,
    DISPLAY_RAW,
    KEY_HINTS,
    MODE_POINT,
)
from ..other import discovery
from ..other.schema import RatingEntry
from ..other.session import EvaluationSession
from . import shortcuts
from .annotation_flow import AnnotationFlowMixin
from .annotations import AnnotationListWidget, EdgeBuilder, EdgeOverlay
from .artifacts_tab import ArtifactsTab
from .compare_tab import ComparisonTab
from .diagnostics_tab import DiagnosticsTab
from .metrics_panel import MetricsPanel
from .panel_grid import PanelGrid
from .queue_panel import QueuePanel
from .scoring_panel import ScoringPanel
from .theme import apply_theme, heading, subtle
from .toolbar import InspectorToolbar
from .viz_tab import VisualizationTab


class _GridHost(QWidget):
    """Holds the panel grid with the cross-panel edge overlay stacked on top,
    keeping the overlay's geometry synced on resize."""

    def __init__(self, grid: PanelGrid, overlay: EdgeOverlay, parent=None):
        super().__init__(parent)
        self._overlay = overlay
        overlay.setParent(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(grid)
        overlay.sync_geometry()

    def resizeEvent(self, event) -> None:  # noqa: D102 - Qt override
        super().resizeEvent(event)
        self._overlay.sync_geometry()


class InspectorWindow(AnnotationFlowMixin, QMainWindow):
    def __init__(
        self,
        base_dir: str,
        out_path: str,
        redo: bool,
        repo_root: str,
        default_display_mode: str = DISPLAY_RAW,
        results_path: Optional[str] = None,
    ):
        super().__init__()
        self.setWindowTitle("ASP Evaluation Inspector")
        self.resize(1760, 1040)
        apply_theme(self)

        self.base_dir = base_dir
        self.repo_root = repo_root
        self.results_path = results_path
        self._assets = None
        self._edge_builder = EdgeBuilder()

        names = discovery.discover_datasets(base_dir)
        self.session = EvaluationSession(names, out_path, redo=redo)
        self.total_datasets = len(names)

        self._build_ui(default_display_mode)
        shortcuts.install(self)
        self.queue_panel.set_session(self.session)
        if self.session.current:
            self._load_current()
        else:
            self.status_label.setText(f"No datasets found under {base_dir}/output/.")

    # -- compatibility -------------------------------------------------------

    @property
    def out_path(self) -> str:
        return self.session.out_path

    @property
    def evaluations(self) -> Dict[str, RatingEntry]:
        return self.session.evaluations

    @property
    def todo(self) -> List[str]:
        """Datasets still lacking a real judgment — the queue the CLI reports."""
        return [n for n in self.session.order if not self.session.is_rated(n)]

    # -- construction --------------------------------------------------------

    def _build_ui(self, default_display_mode: str) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(8, 8, 8, 6)
        outer.setSpacing(6)

        header = QHBoxLayout()
        self.title_label = heading("—")
        self.status_label = subtle("")
        header.addWidget(self.title_label)
        header.addWidget(self.status_label, stretch=1)
        outer.addLayout(header)

        self.toolbar = InspectorToolbar()
        self.toolbar.modeChanged.connect(self._on_mode_changed)
        self.toolbar.displayModeChanged.connect(self._on_display_mode_changed)
        self.toolbar.layoutChanged.connect(self._on_layout_changed)
        self.toolbar.visibilityChanged.connect(self._on_visibility_changed)
        self.toolbar.lockToggled.connect(lambda locked: self.grid.set_locked(locked))
        self.toolbar.fitRequested.connect(self._fit_all)
        self.toolbar.zoomRequested.connect(lambda step: self.grid.zoom_focused(step))
        outer.addWidget(self.toolbar)

        self.grid = PanelGrid()
        self.grid.bboxDrawn.connect(self._on_bbox_drawn)
        self.grid.pointPicked.connect(self._on_point_picked)
        self.grid.pixelHovered.connect(self._on_pixel_hovered)
        self.grid.pixelPinned.connect(self._on_pixel_pinned)
        self.grid.focusChanged.connect(self._on_focus_changed)
        self.overlay = EdgeOverlay()
        self.overlay.register_panels(self.grid.panels)
        grid_host = _GridHost(self.grid, self.overlay)
        self.grid.set_display_mode(default_display_mode)
        self.toolbar.set_display_pixel(default_display_mode == DISPLAY_PIXEL)

        self.tabs = QTabWidget()
        self.viz_tab = VisualizationTab()
        self.compare_tab = ComparisonTab()
        self.diagnostics_tab = DiagnosticsTab(self.repo_root)
        self.metrics_panel = MetricsPanel()
        self.artifacts_tab = ArtifactsTab()
        self.tabs.addTab(self.metrics_panel, "Metrics")
        self.tabs.addTab(self.diagnostics_tab, "Diagnostics")
        self.tabs.addTab(self.compare_tab, "Compare")
        self.tabs.addTab(self.viz_tab, "Visualise")
        self.tabs.addTab(self.artifacts_tab, "Artifacts")

        centre = QSplitter(Qt.Orientation.Vertical)
        centre.addWidget(grid_host)
        centre.addWidget(self.tabs)
        centre.setStretchFactor(0, 3)
        centre.setStretchFactor(1, 2)
        # Explicit sizes as well as stretch factors: the metrics table's size
        # hint is tall enough to win the initial split on its own and squeeze
        # the panorama row down to a filmstrip.
        centre.setSizes([660, 400])

        self.queue_panel = QueuePanel()
        self.queue_panel.datasetSelected.connect(self._on_dataset_selected)

        body = QSplitter(Qt.Orientation.Horizontal)
        body.addWidget(self.queue_panel)
        body.addWidget(centre)
        body.addWidget(self._build_side_panel())
        body.setStretchFactor(0, 0)
        body.setStretchFactor(1, 4)
        body.setStretchFactor(2, 0)
        body.setSizes([230, 1120, 400])
        outer.addWidget(body, stretch=1)

        self.pixel_label = subtle("Pixel: —")
        self.pixel_label.setProperty("role", "mono")
        footer = QHBoxLayout()
        footer.addWidget(self.pixel_label, stretch=1)
        hints = subtle("   ".join(f"{k}: {v}" for k, v in KEY_HINTS))
        hints.setStyleSheet(f"color: {COL_TEXT_DIM}; font-size: 11px;")
        footer.addWidget(hints)
        outer.addLayout(footer)

    def _build_side_panel(self) -> QWidget:
        host = QWidget()
        host.setMinimumWidth(360)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.scoring_panel = ScoringPanel()
        self.scoring_panel.changed.connect(self._on_scoring_changed)
        layout.addWidget(self.scoring_panel, stretch=3)

        layout.addWidget(subtle("Regions & links"))
        self.annotation_list = AnnotationListWidget()
        self.annotation_list.set_remove_callback(self._on_remove_annotation)
        layout.addWidget(self.annotation_list, stretch=1)

        nav = QHBoxLayout()
        nav.setSpacing(4)
        self.back_btn = QPushButton("‹ Back")
        self.back_btn.clicked.connect(self._go_back)
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.setToolTip("Defer this test — it stays in the queue and Back still works")
        self.skip_btn.clicked.connect(self._go_skip)
        self.next_btn = QPushButton("Save & Next ›")
        self.next_btn.setProperty("role", "primary")
        self.next_btn.clicked.connect(self._go_next)
        for btn in (self.back_btn, self.skip_btn, self.next_btn):
            nav.addWidget(btn)
        layout.addLayout(nav)
        return host

    # -- dataset loading -----------------------------------------------------

    def _load_current(self) -> None:
        name = self.session.current
        if name is None:
            return
        self._edge_builder.reset()
        self._assets = discovery.load_test_assets(
            self.base_dir, name, self.repo_root, self.results_path
        )
        images = discovery.load_images(self._assets)
        entry = self.session.entry(name)

        self.grid.set_images(images)
        self.toolbar.set_comparators(self.grid.available(), self.grid.visible())
        self.grid.restore_bboxes(entry.bboxes)
        self.overlay.set_edges(entry.edges)

        self.scoring_panel.set_comparators([k for k in self.grid.available() if k in self.scorable()])
        self.scoring_panel.load_entry(entry)
        self.annotation_list.refresh(entry.bboxes, entry.edges)

        run_label = self._run_label()
        self.metrics_panel.set_metrics(self._assets.metrics, run_label)
        self.diagnostics_tab.set_dataset(name)
        for tab in (self.viz_tab, self.compare_tab, self.diagnostics_tab):
            tab.set_context(images, self._assets.metrics, name)
        self.artifacts_tab.set_assets(self._assets)

        self._update_header()
        self.back_btn.setEnabled(self.session.can_go_back())
        # Panels have no final geometry until the event loop runs, so fitting
        # now would use stale viewport sizes.
        QTimer.singleShot(0, self._fit_all)

    def scorable(self) -> List[str]:
        from ..constants.schema import SCORABLE_KEYS

        return list(SCORABLE_KEYS)

    def _run_label(self) -> str:
        metrics = discovery.load_metrics(self.repo_root, self.results_path)
        metadata = metrics.get("__metadata__") or {}
        timestamp = metadata.get("timestamp", "")
        count = metadata.get("total_datasets")
        if not timestamp:
            return ""
        return f"{timestamp[:16].replace('T', ' ')}, {count} datasets"

    def _update_header(self) -> None:
        name = self.session.current or "—"
        progress = self.session.progress()
        self.title_label.setText(name)
        missing = self.scoring_panel.missing_required()
        state = "complete" if not missing else f"needs {', '.join(missing)}"
        self.status_label.setText(
            f"#{progress.position}/{progress.total} · {progress.rated} rated · "
            f"{progress.skipped} skipped · this test: {state}"
        )
        self.queue_panel.refresh()

    # -- toolbar / view ------------------------------------------------------

    def _on_mode_changed(self, mode: str) -> None:
        self.grid.set_mode(mode)
        if mode != MODE_POINT:
            self._edge_builder.reset()

    def _on_display_mode_changed(self, mode: str) -> None:
        self.grid.set_display_mode(mode)

    def _on_layout_changed(self, mode: str) -> None:
        self.grid.set_layout_mode(mode)
        QTimer.singleShot(0, self._fit_all)

    def _on_visibility_changed(self, keys: list) -> None:
        self.grid.set_visible(keys)
        QTimer.singleShot(0, self._fit_all)

    def _fit_all(self) -> None:
        self.grid.fit_all()
        self.overlay.sync_geometry()
        self.overlay.update()

    def _on_focus_changed(self, key: str) -> None:
        if key:
            self.status_label.setText(
                f"Focused: {COMPARATOR_TITLES.get(key, key)} — 0-4 scores its coherence"
            )

    def _on_pixel_hovered(self, key: str, x: int, y: int, bgr) -> None:
        if bgr is None:
            self.pixel_label.setText("Pixel: —")
            return
        b, g, r = bgr
        self.pixel_label.setText(
            f"{COMPARATOR_TITLES.get(key, key)} ({x}, {y})  R={r:3d} G={g:3d} B={b:3d}  #{r:02x}{g:02x}{b:02x}"
        )

    def _on_pixel_pinned(self, key: str, x: int, y: int, bgr) -> None:
        """Pin a probe and report the same pixel in every other panel, which is
        the actual question being asked when probing a comparison."""
        readings = []
        for other in self.grid.visible():
            panel = self.grid.panels[other]
            img = panel.current_image()
            if img is None:
                continue
            h, w = img.shape[:2]
            # Sample the *proportionally* matching pixel, since canvases differ
            # in size; exact pixel coordinates aren't comparable across them.
            src = self.grid.panels[key].current_image()
            if src is None:
                continue
            sh, sw = src.shape[:2]
            ox, oy = min(w - 1, int(x / sw * w)), min(h - 1, int(y / sh * h))
            bb, gg, rr = (int(v) for v in img[oy, ox])
            readings.append(f"{COMPARATOR_TITLES.get(other, other)}({ox},{oy})=({rr},{gg},{bb})")
        self.pixel_label.setText("Pinned: " + "   ".join(readings))

    # -- scoring / persistence ----------------------------------------------

    def _score_focused(self, value: int) -> None:
        key = self.grid.focus_key()
        if key is None:
            self.status_label.setText("No panel focused — press A, S or Tab first.")
            return
        if not self.scoring_panel.score_focused(key, value):
            self.status_label.setText(f"{COMPARATOR_TITLES.get(key, key)} isn't a scored comparator.")

    def _toggle_defect(self, index: int) -> None:
        key = self.scoring_panel.toggle_defect_index(index)
        if key:
            title = dict((k, t) for k, t, _ in DEFECTS).get(key, key)
            self.status_label.setText(f"Toggled defect tag: {title}")

    def _on_scoring_changed(self) -> None:
        self._commit()
        self._update_header()

    def _commit(self) -> None:
        self.session.commit()

    def _save_now(self) -> None:
        self._commit()
        self.session.save()
        self.status_label.setText(f"Saved to {self.session.out_path}")

    # -- navigation ----------------------------------------------------------

    def _go_next(self) -> None:
        missing = self.scoring_panel.missing_required()
        if missing:
            QMessageBox.warning(
                self, "Incomplete evaluation",
                "Set both ASP and Simple coherence (0-4) before continuing, or press Skip "
                f"to defer this test.\n\nStill missing: {', '.join(missing)}",
            )
            return
        if self.session.accept() is None:
            self._finish("All datasets rated.")
            return
        self._load_current()

    def _go_skip(self) -> None:
        if self.session.advance(skip=True) is None:
            self._finish("Reached the end of the queue.")
            return
        self._load_current()

    def _go_back(self) -> None:
        if self.session.go_back() is None:
            self.status_label.setText("Nothing to go back to.")
            return
        self._load_current()

    def _on_dataset_selected(self, name: str) -> None:
        self.session.go_to(name)
        self._load_current()

    def open_dataset(self, name: str, record_history: bool = False) -> bool:
        """Jump straight to a dataset by name — the public entry the CLI's
        ``--start-at`` and the FiftyOne plugin's handoff use."""
        if name not in self.session.order:
            return False
        self.session.go_to(name, record_history=record_history)
        self._load_current()
        return True

    def _finish(self, message: str) -> None:
        self.session.save()
        progress = self.session.progress()
        self.status_label.setText(
            f"{message} {progress.rated}/{progress.total} rated. Saved to {self.session.out_path}."
        )
        self.queue_panel.refresh()

    def closeEvent(self, event) -> None:  # noqa: D102 - Qt override
        self._commit()
        self.session.save()
        super().closeEvent(event)


# The pre-rebuild name, kept so bench_eval_dispatch.py and its smoke test keep
# working without knowing the window was replaced.
RatingDashboard = InspectorWindow
