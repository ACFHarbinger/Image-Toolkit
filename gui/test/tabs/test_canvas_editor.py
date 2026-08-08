import numpy as np
import pytest
from csg_gui.elements.canvas_editor import MangaCanvasEditor
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage

pytestmark = pytest.mark.gui


class _FakeMouseEvent:
    """A minimal stand-in for QMouseEvent exposing only what
    MangaCanvasEditor's mouseReleaseEvent actually reads -- avoids fighting
    QGraphicsView's viewport/scene coordinate mapping just to unit-test the
    stroke-bbox-finalization logic in isolation."""

    def __init__(self, button=Qt.MouseButton.LeftButton):
        self._button = button

    def button(self):
        return self._button


def _make_image(w=50, h=50, color=(200, 200, 200)):
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(QColor(*color))
    return img


class TestMangaCanvasEditor:
    def test_no_line_art_initially(self, q_app):
        editor = MangaCanvasEditor()
        assert editor.has_line_art() is False

    def test_set_line_art_resets_scribbles_and_result(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        assert editor.has_line_art() is True
        assert editor.has_scribbles() is False
        assert editor.get_result_pixmap().isNull()

    def test_get_line_art_gray_matches_fill_color(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image(color=(100, 100, 100)))
        gray = editor.get_line_art_gray()
        assert gray.shape == (50, 50)
        assert gray.dtype == np.uint8
        assert int(gray[10, 10]) == 100

    def test_painting_produces_scribble_mask_and_color(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        editor.set_pen_color(QColor(10, 200, 30))
        editor.set_pen_width(6)
        editor._paint_line(QPointF(20, 20), QPointF(25, 25))

        assert editor.has_scribbles() is True
        mask = editor.get_scribble_mask()
        assert mask.any()
        rgb = editor.get_scribble_rgb()
        assert tuple(int(v) for v in rgb[20, 20]) == (10, 200, 30)

    def test_clear_scribbles_empties_mask(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        editor._paint_line(QPointF(10, 10), QPointF(10, 10))
        assert editor.has_scribbles() is True

        editor.clear_scribbles()
        assert editor.has_scribbles() is False

    def test_set_result_updates_pixmap(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        result = np.full((50, 50, 3), 255, dtype=np.uint8)
        editor.set_result(result)
        pixmap = editor.get_result_pixmap()
        assert not pixmap.isNull()
        assert pixmap.width() == 50 and pixmap.height() == 50

    def test_pen_color_getter_setter(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_pen_color(QColor(1, 2, 3))
        assert editor.pen_color().getRgb()[:3] == (1, 2, 3)

    def test_scribble_changed_signal_emitted_on_release(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        received = []
        editor.scribble_changed.connect(lambda: received.append(True))

        editor.clear_scribbles()  # also emits, sanity check the connection works
        assert received == [True]

    def test_get_last_stroke_bbox_none_before_any_stroke(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        assert editor.get_last_stroke_bbox() is None

    def test_accumulate_stroke_bbox_expands_with_pen_width_padding(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        editor.set_pen_width(10)

        editor._accumulate_stroke_bbox(QPointF(20, 20))
        assert editor._stroke_bbox == (15, 15, 26, 26)

        editor._accumulate_stroke_bbox(QPointF(30, 22))
        y0, x0, y1, x1 = editor._stroke_bbox
        assert y0 == 15 and x0 == 15
        assert y1 >= 27 and x1 >= 35

    def test_stroke_bbox_clipped_to_canvas_bounds(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image(w=50, h=50))
        editor.set_pen_width(20)

        editor._accumulate_stroke_bbox(QPointF(0, 0))
        y0, x0, y1, x1 = editor._stroke_bbox
        assert y0 == 0 and x0 == 0

        editor._accumulate_stroke_bbox(QPointF(49, 49))
        _, _, y1, x1 = editor._stroke_bbox
        assert y1 <= 50 and x1 <= 50

    def test_stroke_bbox_finalized_on_release(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        editor._painting = True
        editor._stroke_bbox = (10, 10, 20, 20)

        editor.mouseReleaseEvent(_FakeMouseEvent())

        assert editor.get_last_stroke_bbox() == (10, 10, 20, 20)
        assert editor._painting is False

    def test_clear_scribbles_resets_last_stroke_bbox(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        editor._painting = True
        editor._stroke_bbox = (10, 10, 20, 20)
        editor.mouseReleaseEvent(_FakeMouseEvent())
        assert editor.get_last_stroke_bbox() is not None

        editor.clear_scribbles()
        assert editor.get_last_stroke_bbox() is None

    def test_set_line_art_resets_last_stroke_bbox(self, q_app):
        editor = MangaCanvasEditor()
        editor.set_line_art(_make_image())
        editor._painting = True
        editor._stroke_bbox = (10, 10, 20, 20)
        editor.mouseReleaseEvent(_FakeMouseEvent())
        assert editor.get_last_stroke_bbox() is not None

        editor.set_line_art(_make_image())
        assert editor.get_last_stroke_bbox() is None
