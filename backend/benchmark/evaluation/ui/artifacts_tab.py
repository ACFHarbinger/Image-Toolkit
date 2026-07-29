"""Artifacts tab: browse the static PNGs the benchmark already wrote for this
test — ``output/plots/`` (8 diagnostic plots) and ``output/panorama_stages/``
(100+ per-stage renders).

``discovery`` has always resolved ``plots_dir`` and ``stage_dir`` and the old
dashboard never surfaced either (issue #123 defect 7), so the only way to see a
stage render was a file manager. Stage renders are grouped by their
``stageNN_<label>`` prefix, because a flat list of 100+ ``..._frameNN.png`` names
is unusable; picking a group gives a frame slider over its members.

Images load into a zoomable panel, which matters most here: a
``stage11_fg_composite`` render is exactly where a torn-anatomy defect becomes
attributable to a stage.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import cv2
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSlider,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..constants.user_interface import DISPLAY_RAW, MODE_NAVIGATE
from ..other import discovery
from ..other.discovery import TestAssets
from .image_panel import ImagePanel
from .theme import subtle


class ArtifactsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: Dict[str, List[str]] = {}
        self._plots: List[str] = []
        self._current: List[str] = []

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMaximumWidth(280)
        self._tree.currentItemChanged.connect(self._on_selected)

        self._panel = ImagePanel("artifact", "Artifact")
        self._panel.set_mode(MODE_NAVIGATE)
        self._panel.set_display_mode(DISPLAY_RAW)

        self._frame_slider = QSlider(Qt.Orientation.Horizontal)
        self._frame_slider.setRange(0, 0)
        self._frame_slider.valueChanged.connect(self._on_frame_changed)
        self._frame_label = subtle("")

        frame_row = QHBoxLayout()
        frame_row.addWidget(QLabel("Frame"))
        frame_row.addWidget(self._frame_slider, stretch=1)
        frame_row.addWidget(self._frame_label)
        self._frame_row = QWidget()
        self._frame_row.setLayout(frame_row)
        self._frame_row.setVisible(False)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(4)
        self._caption = subtle("Select an artifact.")
        self._caption.setWordWrap(True)
        right.addWidget(self._caption)
        right.addWidget(self._panel, stretch=1)
        right.addWidget(self._frame_row)
        right_host = QWidget()
        right_host.setLayout(right)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)
        outer.addWidget(self._tree)
        outer.addWidget(right_host, stretch=1)

    def set_assets(self, assets: Optional[TestAssets]) -> None:
        self._tree.clear()
        self._panel.set_image(None)
        self._frame_row.setVisible(False)
        self._current = []
        if assets is None:
            self._caption.setText("No test loaded.")
            return

        self._plots = discovery.list_plot_images(assets.plots_dir)
        self._groups = discovery.stage_groups(assets.stage_dir)

        if self._plots:
            root = QTreeWidgetItem([f"Plots ({len(self._plots)})"])
            self._tree.addTopLevelItem(root)
            for path in self._plots:
                child = QTreeWidgetItem([os.path.splitext(os.path.basename(path))[0]])
                child.setData(0, Qt.ItemDataRole.UserRole, [path])
                root.addChild(child)
            root.setExpanded(True)
        if self._groups:
            root = QTreeWidgetItem([f"Pipeline stages ({len(self._groups)})"])
            self._tree.addTopLevelItem(root)
            for prefix, paths in self._groups.items():
                child = QTreeWidgetItem([f"{prefix}  ({len(paths)})"])
                child.setData(0, Qt.ItemDataRole.UserRole, paths)
                root.addChild(child)
            root.setExpanded(True)
        if not self._plots and not self._groups:
            self._caption.setText(
                "This test has no plots or stage renders on disk.\n"
                "They are written per-run under {dataset}/output/{plots,panorama_stages}/."
            )
        else:
            self._caption.setText("Select an artifact.")

    def _on_selected(self, current: Optional[QTreeWidgetItem], _previous) -> None:
        if current is None:
            return
        paths = current.data(0, Qt.ItemDataRole.UserRole)
        if not paths:
            return
        self._current = paths
        multi = len(paths) > 1
        self._frame_row.setVisible(multi)
        self._frame_slider.blockSignals(True)
        self._frame_slider.setRange(0, len(paths) - 1)
        self._frame_slider.setValue(0)
        self._frame_slider.blockSignals(False)
        self._show(0)

    def _on_frame_changed(self, index: int) -> None:
        self._show(index)

    def _show(self, index: int) -> None:
        if not (0 <= index < len(self._current)):
            return
        path = self._current[index]
        img = cv2.imread(path)
        if img is None:
            self._caption.setText(f"Could not decode {os.path.basename(path)}")
            self._panel.set_image(None)
            return
        self._panel.set_image(img)
        self._frame_label.setText(f"{index + 1}/{len(self._current)}")
        self._caption.setText(f"{os.path.basename(path)}   {img.shape[1]}x{img.shape[0]}")
