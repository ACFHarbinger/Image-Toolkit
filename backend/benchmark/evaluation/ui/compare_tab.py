"""Comparison Tools tab: ImageJ/DiffImg/ImageMagick-style ASP-vs-Simple
pixel comparisons, wired onto the shared ``ToolTabBase`` plumbing.
"""

from __future__ import annotations

from ..logic import comparison_maps as cm
from .comparison_widget import SwipeCompareWidget
from .tool_tab_base import ToolTabBase


class ComparisonTab(ToolTabBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._add_button("Abs. Difference (inverted)", self._show_diff)
        self._add_button("SSIM Heatmap", self._show_ssim)
        self._add_button("False-Color Overlay", self._show_false_color)
        self._add_button("Alpha Blend (50%)", self._show_blend)
        self._add_button("Checkerboard Mosaic", self._show_checkerboard)
        self._add_button("Contour-Bounded Diff", self._show_contours)
        self._add_button("Swipe Compare", self._show_swipe)

    def _pair(self):
        return self._asp, self._simple

    def _show_diff(self) -> None:
        a, b = self._pair()
        if a is None or b is None:
            return
        self._show_image(cm.abs_diff_inverted(a, b))

    def _show_ssim(self) -> None:
        a, b = self._pair()
        if a is None or b is None:
            return
        score, heat = cm.ssim_heatmap(a, b)
        self._show_image(heat)

    def _show_false_color(self) -> None:
        a, b = self._pair()
        if a is None or b is None:
            return
        self._show_image(cm.false_color_overlay(a, b))

    def _show_blend(self) -> None:
        a, b = self._pair()
        if a is None or b is None:
            return
        self._show_image(cm.alpha_blend(a, b, 0.5))

    def _show_checkerboard(self) -> None:
        a, b = self._pair()
        if a is None or b is None:
            return
        self._show_image(cm.checkerboard_mosaic(a, b))

    def _show_contours(self) -> None:
        a, b = self._pair()
        if a is None or b is None:
            return
        annotated, _boxes = cm.contour_bounding(a, b)
        self._show_image(annotated)

    def _show_swipe(self) -> None:
        a, b = self._pair()
        if a is None or b is None:
            return
        widget = SwipeCompareWidget()
        widget.set_images(a, b)
        self._show_widget(widget)
