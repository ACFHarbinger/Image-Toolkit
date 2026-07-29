"""
Offscreen smoke tests for the PySide6 evaluation inspector (issue #123).

Runs under ``QT_QPA_PLATFORM=offscreen`` (set before PySide6 is imported), the
same convention ``backend/benchmark/bench_gui_thumbnails.py`` uses — no real
display is needed or used, and no event loop is started.

Deliberately targeted at the defects that had no test before, all of which were
invisible to a "does the window build" check:

  defect 1 — Pixel Value Mode was a no-op: ``set_display_mode`` stored a string
             that nothing ever read, and PIXEL_GRID_ZOOM_THRESHOLD was imported
             and unused.
  defect 6 — zoom was discontinuous, because ``fit_to_view`` set ``_zoom = 1.0``
             while the transform was the fit scale; and sync mirrored only the
             scale factor, never the scroll offset, so panned panels drifted.
  defect 8 — the panel row was hard-wired to exactly three comparators.
  defect 9 — the pair visualisations ignored the source selector.
  defect 10 — results were hard-scaled into a QLabel with no zoom.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

pytest.importorskip("PySide6", reason="the inspector needs PySide6")

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from backend.benchmark.evaluation.constants.user_interface import (  # noqa: E402
    DISPLAY_PIXEL,
    DISPLAY_RAW,
    LAYOUT_GRID,
    LAYOUT_STACK,
    MODE_BBOX,
    MODE_PROBE,
    PIXEL_GRID_ZOOM_THRESHOLD,
    ZOOM_MAX,
    ZOOM_MIN,
)
from backend.benchmark.evaluation.ui.image_panel import ImagePanel  # noqa: E402
from backend.benchmark.evaluation.ui.panel_grid import PanelGrid  # noqa: E402
from backend.benchmark.evaluation.ui.scoring_panel import ScoringPanel  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _image(h=400, w=300, value=90) -> np.ndarray:
    img = np.full((h, w, 3), value, dtype=np.uint8)
    img[h // 2:, :] = value + 60  # a horizontal seam to look at
    return img


@pytest.fixture()
def panel(qapp):
    widget = ImagePanel("asp", "ASP")
    widget.resize(320, 240)
    # show() so the viewport reaches its final geometry — an unshown
    # QAbstractScrollArea keeps a default viewport size, which would make the
    # fit-scale assertions below measure the wrong box.
    widget.show()
    qapp.processEvents()
    widget.set_image(_image())
    yield widget
    widget.close()


def _expected_fit_scale(widget: ImagePanel) -> float:
    size = widget.viewport().size()
    w, h = widget.image_size()
    return min(size.width() / w, size.height() / h)


# ---------------------------------------------------------------------------
# defect 6 — zoom must be continuous from the fitted view
# ---------------------------------------------------------------------------


def test_fit_sets_zoom_to_one_and_native_scale_to_the_fit_scale(panel):
    panel.fit_to_view()
    assert panel.zoom() == pytest.approx(1.0)
    # The old bug: _zoom said 1.0 while the real device scale was the fit scale,
    # so the two disagreed and the first wheel notch jumped straight to native
    # 1.15x. The two must now be consistent by construction.
    assert panel.native_scale() == pytest.approx(_expected_fit_scale(panel), rel=1e-6)


def test_one_zoom_step_scales_the_fitted_view_not_the_native_size(panel):
    panel.fit_to_view()
    fit_scale = panel.native_scale()
    panel.set_zoom(panel.zoom() * 1.15)
    assert panel.zoom() == pytest.approx(1.15)
    # Continuous: 1.15x the *fitted* scale. The old behaviour landed on 1.15
    # native regardless of the fit, which on a 1700px panorama is a violent jump.
    assert panel.native_scale() == pytest.approx(fit_scale * 1.15, rel=1e-3)


def test_zoom_of_a_large_panorama_starts_far_below_native(qapp):
    """The case that made defect 6 visible: a benchmark panorama is ~1700-2000px
    on its long edge, so its fitted view is a small fraction of native."""
    widget = ImagePanel("asp", "ASP")
    widget.resize(400, 300)
    widget.show()
    qapp.processEvents()
    widget.set_image(_image(1704, 1703))
    try:
        assert widget.zoom() == pytest.approx(1.0)
        assert widget.native_scale() < 0.3
        widget.set_zoom(1.15)
        assert widget.native_scale() < 0.35
    finally:
        widget.close()


@pytest.mark.parametrize("requested,expected", [(1e-6, ZOOM_MIN), (1e6, ZOOM_MAX)])
def test_zoom_is_clamped(panel, requested, expected):
    panel.set_zoom(requested)
    assert panel.zoom() == pytest.approx(expected)


def test_external_view_does_not_re_broadcast(panel):
    """The guard that stops a locked pair from looping."""
    seen = []
    panel.viewChanged.connect(lambda *args: seen.append(args))
    panel.apply_external_view(2.0, 0.5, 0.5)
    assert seen == []
    assert panel.zoom() == pytest.approx(2.0)


def test_zoom_emits_the_normalized_centre_so_pan_can_be_mirrored(panel):
    seen = []
    panel.viewChanged.connect(lambda z, cx, cy: seen.append((z, cx, cy)))
    panel.set_zoom(3.0)
    assert seen
    zoom, cx, cy = seen[-1]
    assert zoom == pytest.approx(3.0)
    assert 0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0


# ---------------------------------------------------------------------------
# defect 1 — Pixel Value Mode
# ---------------------------------------------------------------------------


def test_display_mode_round_trips(panel):
    assert panel.display_mode() == DISPLAY_RAW
    panel.set_display_mode(DISPLAY_PIXEL)
    assert panel.display_mode() == DISPLAY_PIXEL


def test_pixel_overlay_paints_without_error_above_the_grid_threshold(panel, qapp):
    """The old mode stored the string and repainted; nothing read it. Rendering
    the viewport exercises drawForeground's grid + numeric-label path."""
    from PySide6.QtGui import QPainter, QPixmap

    panel.set_display_mode(DISPLAY_PIXEL)
    panel.set_zoom(400.0)  # comfortably past the text threshold too
    assert panel.native_scale() > PIXEL_GRID_ZOOM_THRESHOLD
    target = QPixmap(panel.viewport().size())
    target.fill()
    painter = QPainter(target)
    panel.render(painter)
    painter.end()


def test_pixel_probe_reports_the_underlying_value(panel):
    found = panel.pixel_at(QPoint(panel.viewport().width() // 2, panel.viewport().height() // 2))
    assert found is not None
    x, y, bgr = found
    assert 0 <= x < 300 and 0 <= y < 400
    assert tuple(bgr) in {(90, 90, 90), (150, 150, 150)}


def test_pixel_probe_off_image_returns_none(panel):
    assert panel.pixel_at(QPoint(-50, -50)) is None


def test_pinning_a_pixel_emits_its_value(panel):
    seen = []
    panel.pixelPinned.connect(lambda x, y, bgr: seen.append((x, y, bgr)))
    panel.set_mode(MODE_PROBE)
    panel._pin_pixel(QPoint(panel.viewport().width() // 2, panel.viewport().height() // 2))
    assert len(seen) == 1


def test_pixel_region_crops_a_normalized_rect(panel):
    region = panel.pixel_region(0.0, 0.0, 0.5, 0.25)
    assert region is not None
    assert region.shape[0] == pytest.approx(100, abs=1) and region.shape[1] == pytest.approx(150, abs=1)


def test_pixel_region_of_a_degenerate_rect_is_none(panel):
    assert panel.pixel_region(0.5, 0.5, 0.0, 0.0) is None


def test_visible_region_is_normalized_and_bounded(panel):
    panel.fit_to_view()
    region = panel.visible_region_norm()
    assert region is not None
    x, y, w, h = region
    assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
    assert 0.0 < w <= 1.0 and 0.0 < h <= 1.0


# ---------------------------------------------------------------------------
# Annotation geometry
# ---------------------------------------------------------------------------


def test_bbox_is_emitted_in_normalized_coordinates(panel):
    from PySide6.QtCore import QRectF

    seen = []
    panel.bboxDrawn.connect(seen.append)
    panel.set_mode(MODE_BBOX)
    panel._finish_bbox(QRectF(30, 100, 150, 200))  # scene (= image pixel) coords
    assert len(seen) == 1
    data = seen[0]
    assert data["x"] == pytest.approx(30 / 300)
    assert data["y"] == pytest.approx(100 / 400)
    assert data["w"] == pytest.approx(150 / 300)
    assert data["h"] == pytest.approx(200 / 400)


def test_restoring_bboxes_after_a_reload_does_not_accumulate(panel):
    from backend.benchmark.evaluation.other.schema import BoundingBox

    boxes = [BoundingBox(image="asp", x=0.1, y=0.1, w=0.2, h=0.2)]
    panel.restore_bboxes(boxes)
    first = len(panel._overlay_items)
    panel.clear_overlays()
    panel.restore_bboxes(boxes)
    assert len(panel._overlay_items) == first


def test_bboxes_for_other_panels_are_ignored(panel):
    from backend.benchmark.evaluation.other.schema import BoundingBox

    panel.restore_bboxes([BoundingBox(image="simple", x=0.1, y=0.1, w=0.2, h=0.2)])
    assert panel._overlay_items == []


def test_a_panel_with_no_image_is_inert(qapp):
    empty = ImagePanel("hugin", "Hugin")
    empty.set_image(None)
    assert empty.has_image() is False
    assert empty.image_size() is None
    assert empty.pixel_region(0, 0, 1, 1) is None
    assert empty.visible_region_norm() is None
    empty.fit_to_view()  # must not raise
    empty.set_zoom(4.0)


# ---------------------------------------------------------------------------
# defect 8 — N-way grid
# ---------------------------------------------------------------------------


@pytest.fixture()
def grid(qapp):
    widget = PanelGrid()
    widget.resize(1200, 400)
    widget.set_images({
        "asp": _image(), "simple": _image(420, 320, 100),
        "overmix": _image(500, 380, 110), "ground_truth": _image(440, 300, 120),
    })
    return widget


def test_grid_shows_every_available_comparator(grid):
    assert grid.available() == ["asp", "simple", "overmix", "ground_truth"]
    assert grid.visible() == ["asp", "simple", "overmix", "ground_truth"]


def test_grid_drops_comparators_a_test_lacks(grid):
    grid.set_images({"asp": _image(), "simple": _image()})
    assert grid.available() == ["asp", "simple"]
    assert grid.visible() == ["asp", "simple"]
    assert grid.panels["overmix"].has_image() is False


def test_visibility_selection_keeps_display_order(grid):
    grid.set_visible(["ground_truth", "asp"])
    assert grid.visible() == ["asp", "ground_truth"]


@pytest.mark.parametrize("mode", [LAYOUT_GRID, LAYOUT_STACK])
def test_layout_modes_apply(grid, mode):
    grid.set_layout_mode(mode)
    assert grid.layout_mode() == mode


def test_locking_mirrors_zoom_and_centre_across_panels(grid):
    grid.set_locked(True)
    grid.set_focus("asp")
    grid.panels["asp"].set_zoom(4.0)
    for key in grid.visible():
        assert grid.panels[key].zoom() == pytest.approx(4.0)


def test_locked_panels_share_a_normalized_centre_despite_different_canvases(grid):
    grid.set_locked(True)
    grid.set_focus("asp")
    grid.panels["asp"].set_zoom(6.0)
    centres = [grid.panels[k].center_norm() for k in grid.visible()]
    xs = [c[0] for c in centres]
    ys = [c[1] for c in centres]
    assert max(xs) - min(xs) < 0.1
    assert max(ys) - min(ys) < 0.1


def test_unlocking_leaves_other_panels_alone(grid):
    grid.set_locked(False)
    grid.panels["simple"].set_zoom(1.0)
    grid.panels["asp"].set_zoom(5.0)
    assert grid.panels["simple"].zoom() == pytest.approx(1.0)


def test_focus_cycles_only_through_visible_panels(grid):
    grid.set_visible(["asp", "simple"])
    grid.set_focus("asp")
    grid.cycle_focus(1)
    assert grid.focus_key() == "simple"
    grid.cycle_focus(1)
    assert grid.focus_key() == "asp"


def test_fit_all_resets_every_visible_panel(grid):
    grid.panels["asp"].set_zoom(8.0)
    grid.fit_all()
    assert all(grid.panels[k].zoom() == pytest.approx(1.0) for k in grid.visible())


# ---------------------------------------------------------------------------
# Scoring panel
# ---------------------------------------------------------------------------


@pytest.fixture()
def scoring(qapp):
    widget = ScoringPanel()
    widget.set_comparators(["asp", "simple", "overmix"])
    from backend.benchmark.evaluation.other.schema import RatingEntry

    widget.load_entry(RatingEntry())
    return widget


def test_keyboard_scoring_updates_the_entry(scoring):
    assert scoring.score_focused("asp", 3) is True
    assert scoring.entry().asp == 3
    assert scoring.blocks["asp"].rows["coherence"].score() == 3


def test_scoring_an_absent_comparator_reports_failure(scoring):
    assert scoring.score_focused("hugin", 3) is False


def test_only_coherence_is_required(scoring):
    assert scoring.missing_required() == ["ASP coherence", "Simple coherence"]
    scoring.score_focused("asp", 2)
    scoring.score_focused("simple", 4)
    assert scoring.missing_required() == []


def test_optional_dimensions_do_not_block_completion(scoring):
    scoring.score_focused("asp", 2)
    scoring.score_focused("simple", 4)
    scoring.score_focused("asp", 1, dimension="sharpness")
    assert scoring.missing_required() == []
    assert scoring.entry().score("asp", "sharpness") == 1


def test_preference_toggles_off_when_reselected(scoring):
    scoring.set_preference("asp")
    assert scoring.entry().preference == "asp"
    scoring.set_preference("asp", toggle=True)
    assert scoring.entry().preference is None


def test_defect_tags_toggle_by_index(scoring):
    key = scoring.toggle_defect_index(0)
    assert key == "torn_anatomy"
    assert scoring.entry().defects == ["torn_anatomy"]
    scoring.toggle_defect_index(0)
    assert scoring.entry().defects == []


def test_out_of_range_defect_index_is_ignored(scoring):
    assert scoring.toggle_defect_index(99) is None


def test_collapsed_dimensions_still_show_a_scored_row(scoring):
    """Collapsing must never hide recorded data.

    Asserted with isHidden() rather than isVisible(): the latter is False for
    any widget whose ancestors aren't shown, so on an unshown panel it would
    pass for the wrong reason. isHidden() reflects the explicit setVisible state.
    """
    scoring.score_focused("asp", 3, dimension="seams")
    scoring.blocks["asp"].set_detailed(False)
    assert scoring.blocks["asp"].rows["seams"].isHidden() is False
    assert scoring.blocks["asp"].rows["framing"].isHidden() is True
    assert scoring.blocks["asp"].rows["coherence"].isHidden() is False


def test_expanding_dimensions_shows_every_row(scoring):
    scoring.blocks["asp"].set_detailed(True)
    assert all(not row.isHidden() for row in scoring.blocks["asp"].rows.values())


def test_loading_an_entry_does_not_emit_changes(scoring):
    from backend.benchmark.evaluation.other.schema import RatingEntry

    seen = []
    scoring.changed.connect(lambda: seen.append(1))
    entry = RatingEntry()
    entry.set_score("asp", "coherence", 4)
    scoring.load_entry(entry)
    assert seen == []


def test_comparators_are_rebuilt_per_test(scoring):
    scoring.set_comparators(["asp", "simple"])
    assert set(scoring.blocks) == {"asp", "simple"}
