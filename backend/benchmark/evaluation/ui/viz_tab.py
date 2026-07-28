"""Visualizations tab: buttons for every per-image / cross-image pixel-data
visualization, wired onto ``ToolTabBase``'s shared button-row/result-area
plumbing. A source selector picks which loaded image(s) a button acts on.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel

from ..logic import visualizations_basic as vb
from ..logic import visualizations_matching as vm
from .tool_tab_base import ToolTabBase


class VisualizationTab(ToolTabBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Source image:"))
        self._source = QComboBox()
        self._source.addItems(["ASP", "Simple", "Ground Truth"])
        source_row.addWidget(self._source)
        self._outer.insertLayout(0, source_row)

        self._add_button("Color Histogram", lambda: self._run_single(vb.color_histogram_figure))
        self._add_button("Cumulative Histogram", lambda: self._run_single(vb.cumulative_histogram_figure))
        self._add_button("2D Scatter (RG)", lambda: self._run_single(vb.scatter_2d_figure))
        self._add_button("3D Scatter (RGB)", lambda: self._run_single(vb.scatter_3d_figure))
        self._add_button("Spatial Scatter (edges)", lambda: self._run_single(vb.spatial_scatter_figure))
        self._add_button("Intensity Heatmap", lambda: self._run_single(vb.intensity_heatmap_figure))
        self._add_button("Gradient Heatmap", lambda: self._run_single(vb.gradient_heatmap_figure))
        self._add_button("FFT Spectrum", lambda: self._run_single(vb.fft_magnitude_figure))
        self._add_button("ORB Feature Matches", lambda: self._run_pair(lambda a, b: vm.feature_match_figure(a, b, "orb")))
        self._add_button("SIFT Feature Matches", lambda: self._run_pair(lambda a, b: vm.feature_match_figure(a, b, "sift")))
        self._add_button("Optical Flow (HSV)", lambda: self._run_pair(vm.optical_flow_hsv_figure))

    def _selected_image(self):
        idx = self._source.currentIndex()
        return (self._asp, self._simple, self._gt)[idx]

    def _run_single(self, fn) -> None:
        img = self._selected_image()
        if img is None:
            return
        self._show_figure(fn(img))

    def _run_pair(self, fn) -> None:
        if self._asp is None or self._simple is None:
            return
        self._show_figure(fn(self._asp, self._simple))
