"""RatingDashboard: the top-level PySide6 window tying every panel,
visualization/comparison tab, and the scoring/annotation/save flow
together. This is the module ``evaluation_manager.py`` constructs and runs;
everything else in this package is a component it assembles.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..other import discovery
from ..other.schema import BoundingBox, RatingEntry, load_evaluations, save_evaluations
from .annotations import AnnotationListWidget, EdgeBuilder, EdgeOverlay
from .compare_tab import ComparisonTab
from .panel_base import DISPLAY_PIXEL, DISPLAY_RAW, MODE_BBOX, MODE_NAVIGATE, MODE_POINT, ImagePanel
from .scoring_panel import ScoringPanel
from .viz_tab import VisualizationTab


class _PanelRow(QWidget):
    """QHBoxLayout row of panels with a transparent overlay stacked on top
    for cross-panel edge lines; keeps the overlay geometry synced on resize."""

    def __init__(self, overlay: EdgeOverlay, parent=None):
        super().__init__(parent)
        self._overlay = overlay
        overlay.setParent(self)

    def resizeEvent(self, event) -> None:  # noqa: D102 - Qt override
        super().resizeEvent(event)
        self._overlay.sync_geometry()
        self._overlay.raise_()


class RatingDashboard(QMainWindow):
    def __init__(
        self,
        base_dir: str,
        out_path: str,
        redo: bool,
        repo_root: str,
        default_display_mode: str = DISPLAY_RAW,
    ):
        super().__init__()
        self.setWindowTitle("ASP Coherence Evaluation Dashboard")
        self.resize(1600, 1000)

        self.base_dir = base_dir
        self.out_path = out_path
        self.repo_root = repo_root
        self.evaluations: Dict[str, RatingEntry] = load_evaluations(out_path)

        all_names = discovery.discover_datasets(base_dir)
        self.todo = [n for n in all_names if redo or n not in self.evaluations]
        self.total_datasets = len(all_names)
        self.idx = 0
        self._history: list = []
        self._current_name: Optional[str] = None
        self._edge_builder = EdgeBuilder()
        self._sync_zoom = False

        self._build_ui(default_display_mode)
        if self.todo:
            self._load_dataset(self.todo[0])
        else:
            self.progress_label.setText(f"All {self.total_datasets} dataset(s) already rated in {out_path}.")

    # -- UI construction -----------------------------------------------------

    def _build_ui(self, default_display_mode: str) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        self.progress_label = QLabel("")
        outer.addWidget(self.progress_label)
        outer.addLayout(self._build_toolbar())

        self._overlay = EdgeOverlay()
        panel_row = _PanelRow(self._overlay)
        row_layout = QHBoxLayout(panel_row)
        self.panels: Dict[str, ImagePanel] = {}
        for key, title in (("asp", "ASP"), ("simple", "Simple (SCANS)"), ("ground_truth", "Ground Truth")):
            panel = ImagePanel(key, title)
            panel.zoomChanged.connect(lambda f, k=key: self._on_zoom_changed(k, f))
            panel.bboxDrawn.connect(lambda data, k=key: self._on_bbox_drawn(k, data))
            panel.pointPicked.connect(lambda x, y, k=key: self._on_point_picked(k, x, y))
            panel.pixelHovered.connect(lambda x, y, bgr, k=key: self._on_pixel_hovered(k, x, y, bgr))
            self._overlay.register_panel(key, panel)
            self.panels[key] = panel
            col = QVBoxLayout()
            col.addWidget(QLabel(title))
            col.addWidget(panel)
            row_layout.addLayout(col)
        self.set_display_mode(default_display_mode)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(panel_row)

        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        self.tabs = QTabWidget()
        self.viz_tab = VisualizationTab()
        self.compare_tab = ComparisonTab()
        self.tabs.addTab(self.viz_tab, "Visualizations")
        self.tabs.addTab(self.compare_tab, "Comparison Tools")
        bottom_layout.addWidget(self.tabs, stretch=2)

        side = QVBoxLayout()
        self.scoring_panel = ScoringPanel()
        self.scoring_panel.evaluationChanged.connect(self._persist_current_entry)
        self.scoring_panel.notesChanged.connect(lambda _: self._persist_current_entry())
        side.addWidget(self.scoring_panel)

        self.annotation_list = AnnotationListWidget()
        self.annotation_list.set_remove_callback(self._on_remove_annotation)
        side.addWidget(self.annotation_list)
        side.addLayout(self._build_nav_buttons())
        bottom_layout.addLayout(side, stretch=1)

        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, stretch=1)

        self.pixel_label = QLabel("Pixel: —")
        outer.addWidget(self.pixel_label)

    def _build_toolbar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Tool:"))
        self.tool_combo = QComboBox()
        self.tool_combo.addItems(["Navigate", "Draw BBox", "Pick Edge Point"])
        self.tool_combo.currentIndexChanged.connect(self._on_tool_changed)
        bar.addWidget(self.tool_combo)

        bar.addWidget(QLabel("Display:"))
        self.display_combo = QComboBox()
        self.display_combo.addItems(["Display Mode", "Pixel Value Mode"])
        self.display_combo.currentIndexChanged.connect(
            lambda i: self.set_display_mode(DISPLAY_RAW if i == 0 else DISPLAY_PIXEL)
        )
        bar.addWidget(self.display_combo)

        self.sync_zoom_check = QCheckBox("Synchronized zoom")
        self.sync_zoom_check.toggled.connect(self._on_sync_zoom_toggled)
        bar.addWidget(self.sync_zoom_check)

        fit_btn = QPushButton("Fit all")
        fit_btn.clicked.connect(lambda: [p.fit_to_view() for p in self.panels.values()])
        bar.addWidget(fit_btn)
        bar.addStretch(1)
        return bar

    def _build_nav_buttons(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        back_btn = QPushButton("< Back")
        back_btn.clicked.connect(self._go_back)
        skip_btn = QPushButton("Skip")
        skip_btn.clicked.connect(self._go_skip)
        next_btn = QPushButton("Save & Next >")
        next_btn.clicked.connect(self._go_next)
        quit_btn = QPushButton("Quit")
        quit_btn.clicked.connect(self.close)
        for b in (back_btn, skip_btn, next_btn, quit_btn):
            bar.addWidget(b)
        return bar

    # -- dataset loading -------------------------------------------------------

    def _load_dataset(self, name: str) -> None:
        self._current_name = name
        assets = discovery.load_test_assets(self.base_dir, name, self.repo_root)
        self._asp_img = discovery.imread_bgr(assets.asp_path)
        self._simple_img = discovery.imread_bgr(assets.simple_path)
        self._gt_img = discovery.imread_bgr(assets.gt_path)

        self._redraw_panels()
        self.viz_tab.set_images(self._asp_img, self._simple_img, self._gt_img)
        self.compare_tab.set_images(self._asp_img, self._simple_img, self._gt_img)

        entry = self.evaluations.get(name, RatingEntry())
        self.scoring_panel.load_entry(entry.asp, entry.simple, entry.notes)
        self.annotation_list.refresh(entry.bboxes, entry.edges)
        self._overlay.set_edges(entry.edges)

        pos = self.todo.index(name) + 1 if name in self.todo else 0
        self.progress_label.setText(
            f"{name}  —  {pos}/{len(self.todo)} to rate ({len(self.evaluations)}/{self.total_datasets} rated overall)"
        )

    def _redraw_panels(self) -> None:
        entry = self.evaluations.get(self._current_name, RatingEntry()) if self._current_name else RatingEntry()
        images = {"asp": self._asp_img, "simple": self._simple_img, "ground_truth": self._gt_img}
        for key, panel in self.panels.items():
            panel.set_image(images[key])
            panel.restore_bboxes(entry.bboxes)

    def _current_entry(self) -> RatingEntry:
        if self._current_name is None:
            return RatingEntry()
        return self.evaluations.setdefault(self._current_name, RatingEntry())

    # -- annotation events -----------------------------------------------------

    def _on_bbox_drawn(self, key: str, data: dict) -> None:
        entry = self._current_entry()
        entry.bboxes.append(BoundingBox(image=key, x=data["x"], y=data["y"], w=data["w"], h=data["h"], label=data["label"]))
        self.annotation_list.refresh(entry.bboxes, entry.edges)
        self._persist_current_entry()

    def _on_point_picked(self, key: str, x: float, y: float) -> None:
        edge = self._edge_builder.add_point(key, x, y, self)
        if edge is None:
            return
        entry = self._current_entry()
        entry.edges.append(edge)
        self._overlay.set_edges(entry.edges)
        self.annotation_list.refresh(entry.bboxes, entry.edges)
        self._persist_current_entry()

    def _on_remove_annotation(self, kind: str, idx: int) -> None:
        entry = self._current_entry()
        target = entry.bboxes if kind == "bbox" else entry.edges
        if 0 <= idx < len(target):
            del target[idx]
        self._redraw_panels()
        self._overlay.set_edges(entry.edges)
        self.annotation_list.refresh(entry.bboxes, entry.edges)
        self._persist_current_entry()

    def _on_tool_changed(self, index: int) -> None:
        mode = (MODE_NAVIGATE, MODE_BBOX, MODE_POINT)[index]
        for panel in self.panels.values():
            panel.set_mode(mode)
        if mode != MODE_POINT:
            self._edge_builder.reset()

    def set_display_mode(self, mode: str) -> None:
        for panel in self.panels.values():
            panel.set_display_mode(mode)

    def _on_sync_zoom_toggled(self, checked: bool) -> None:
        self._sync_zoom = checked

    def _on_zoom_changed(self, source_key: str, factor: float) -> None:
        if not self._sync_zoom:
            return
        for key, panel in self.panels.items():
            if key != source_key:
                panel.apply_external_zoom(factor)

    def _on_pixel_hovered(self, key: str, x: int, y: int, bgr) -> None:
        if bgr is None:
            self.pixel_label.setText("Pixel: —")
        else:
            b, g, r = bgr
            self.pixel_label.setText(f"Pixel [{key}] ({x}, {y}): R={r} G={g} B={b}")

    # -- scoring persistence ---------------------------------------------------

    def _persist_current_entry(self) -> None:
        if self._current_name is None:
            return
        entry = self._current_entry()
        entry.asp = self.scoring_panel.asp_score()
        entry.simple = self.scoring_panel.simple_score()
        entry.notes = self.scoring_panel.notes()
        save_evaluations(self.out_path, self.evaluations)

    # -- navigation --------------------------------------------------------

    def _go_next(self) -> None:
        self._persist_current_entry()
        entry = self.evaluations.get(self._current_name)
        if entry is None or entry.asp is None or entry.simple is None:
            QMessageBox.warning(self, "Incomplete evaluation", "Rate both ASP and Simple (0-4) before continuing.")
            return
        self._history.append(self._current_name)
        self._advance()

    def _go_skip(self) -> None:
        self._advance()

    def _go_back(self) -> None:
        if not self._history:
            return
        prev = self._history.pop()
        self._load_dataset(prev)

    def _advance(self) -> None:
        if self._current_name in self.todo:
            pos = self.todo.index(self._current_name)
            remaining = [n for n in self.todo[pos + 1:] if n not in self.evaluations]
        else:
            remaining = [n for n in self.todo if n not in self.evaluations]
        if remaining:
            self._load_dataset(remaining[0])
        else:
            self.progress_label.setText(f"All datasets rated. Saved to {self.out_path}.")

    def closeEvent(self, event) -> None:  # noqa: D102 - Qt override
        self._persist_current_entry()
        super().closeEvent(event)
