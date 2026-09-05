"""Tests for the virtualized gallery prototype — GUI/UX §2.1 Option A.

Verifies the property that motivates Option A over the bounded-page
QLabel grid: a multi-thousand-item gallery costs the same in widgets/paints
as a small one because Qt's QListView viewport culling only ever requests
decorations for visible cells. Also covers lazy background thumbnail loads,
stale-load rejection after reset/cancel, scroll prefetch, selection, and the
composite widget's tab-facing API.

Uses an injectable fake loader worker so no real image files or native
imaging are needed; loads are deterministic.
"""

from __future__ import annotations

import os
import threading
import time

import pytest
from gui.src.components.virtual_gallery import (
    VirtualDualGallery,
    VirtualGallery,
    VirtualGalleryModel,
    VirtualGalleryView,
)
from PySide6.QtCore import QObject, QPoint, QPointF, QRunnable, Qt, Signal
from PySide6.QtGui import QImage, QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget

pytestmark = pytest.mark.gui

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# --- Deterministic fake loader -----------------------------------------------

_BLOCK = threading.Event()   # set to hold fake workers before their run()
_FAIL_PATHS: set = set()     # paths whose fake worker emits a null QImage
_STARTED = threading.Event()  # set when a fake worker enters run()


class _FakeLoaderSignals(QObject):
    result = Signal(str, QImage)


class _FakeLoaderWorker(QRunnable):
    def __init__(self, path: str, target_size: int):
        super().__init__()
        self.path = path
        self.target_size = target_size
        self.signals = _FakeLoaderSignals()
        self.load_generation = 0
        self._stopped = False
        self.setAutoDelete(True)

    def stop(self):
        self._stopped = True

    def run(self):
        _STARTED.set()
        # Poll while _BLOCK is set (Event.wait() returns immediately when the
        # flag is already true, so it can't be used as a "hold" barrier).
        while _BLOCK.is_set() and not self._stopped:
            time.sleep(0.005)
        if self._stopped:
            return
        if self.path in _FAIL_PATHS:
            self.signals.result.emit(self.path, QImage())
            return
        img = QImage(self.target_size, self.target_size, QImage.Format.Format_RGB32)
        img.fill(Qt.GlobalColor.green)
        self.signals.result.emit(self.path, img)


def _make_model(fill_mode: bool = True) -> VirtualGalleryModel:
    return VirtualGalleryModel(worker_factory=_FakeLoaderWorker, fill_mode=fill_mode)


def _pump(model: VirtualGalleryModel) -> None:
    model.thread_pool.waitForDone()
    QApplication.processEvents()


# --- Basic model surface -----------------------------------------------------


def test_row_count_reflects_full_list():
    model = _make_model()
    paths = [f"/p/{i:04d}.png" for i in range(10_000)]
    model.set_paths(paths)
    assert model.rowCount() == 10_000
    assert model.path_at(0) == "/p/0000.png"
    assert model.path_at(9_999) == "/p/9999.png"
    assert model.row_for_path("/p/1234.png") == 1234
    assert model.row_for_path("/missing.png") == -1


def test_clear_resets_rows():
    model = _make_model()
    model.set_paths(["/a.png", "/b.png"])
    model.set_selected(["/a.png"])
    model.set_preview(["/b.png"])
    model.clear()
    assert model.rowCount() == 0
    assert model.is_selected("/a.png") is False
    assert model.is_preview("/b.png") is False


# --- Selected / preview state marks -------------------------------------------


def test_selected_marks_roles_and_data():
    model = _make_model()
    model.set_paths(["/a.png", "/b.png", "/c.png"])
    assert model.is_selected("/a.png") is False
    assert model.data(model.index(0, 0), model.SelectedRole) is False

    model.set_selected(["/a.png", "/b.png"])
    assert model.is_selected("/a.png") is True
    assert model.data(model.index(0, 0), model.SelectedRole) is True
    assert model.data(model.index(1, 0), model.SelectedRole) is True
    assert model.data(model.index(2, 0), model.SelectedRole) is False

    model.mark_selected("/a.png", False)
    assert model.is_selected("/a.png") is False
    assert model.is_selected("/b.png") is True


def test_preview_marks_roles_and_data():
    model = _make_model()
    model.set_paths(["/a.png", "/b.png"])
    model.set_preview(["/b.png"])
    assert model.is_preview("/b.png") is True
    assert model.data(model.index(1, 0), model.PreviewRole) is True
    assert model.data(model.index(0, 0), model.PreviewRole) is False

    model.mark_preview("/b.png", False)
    assert model.is_preview("/b.png") is False


def test_marks_persist_across_set_paths():
    """Selection/preview marks survive a gallery refresh (set_paths); only an
    explicit clear() resets them, so an open preview stays highlighted when
    the gallery repopulates."""
    model = _make_model()
    model.set_paths(["/a.png"])
    model.set_selected(["/a.png"])
    model.set_preview(["/a.png"])
    model.set_paths(["/a.png", "/b.png"])
    assert model.is_selected("/a.png") is True
    assert model.is_preview("/a.png") is True


# --- Delegate border painting -------------------------------------------------


def test_delegate_paints_state_borders():
    from gui.src.components.virtual_gallery.delegate import VirtualGalleryDelegate
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QStyle, QStyleOptionViewItem

    model = _make_model()
    model.set_paths(["/none.png", "/sel.png", "/prev.png"])
    model.set_in_db(["/none.png"])
    model.set_selected(["/sel.png"])
    model.set_preview(["/prev.png"])

    delegate = VirtualGalleryDelegate()
    cases = {
        "/none.png": "#2ecc71",
        "/sel.png": "#5865f2",
        "/prev.png": "#f39c12",
    }
    for row in range(model.rowCount()):
        pm = QPixmap(200, 200)
        pm.fill(Qt.GlobalColor.black)
        painter = QPainter(pm)
        opt = QStyleOptionViewItem()
        opt.rect = pm.rect()
        opt.state = QStyle.StateFlag.State_None
        delegate.paint(painter, opt, model.index(row, 0))
        painter.end()

        expected = cases[model.path_at(row)]
        # Sample a pixel just inside the top border (border width 3/4 px).
        sample = pm.toImage().pixelColor(100, 2)
        if expected is None:
            assert sample.name() == "#000000"
        else:
            assert sample.name() == expected


# --- Composite widget API ----------------------------------------------------


def test_large_gallery_creates_no_card_widgets():
    """A 10k-item gallery must not materialize one widget per item.

    The QLabel grid this replaces would create 10k cards (and cap page size
    precisely because of that). The model/view surface must be widget-free
    apart from the QListView itself.
    """
    model = _make_model()
    view = VirtualGalleryView()
    view.setModel(model)
    model.set_paths([f"/p/{i:04d}.png" for i in range(10_000)])
    view.show()
    QApplication.processEvents()

    from PySide6.QtWidgets import QLabel

    assert view.findChildren(QLabel) == []
    assert not hasattr(model, "path_to_label_map")
    assert model.rowCount() == 10_000
    # Row surface is cheap Python list data, not widgets.
    assert view.model() is model
    view.close()


def test_decoration_request_is_lazy():
    """Without the eager fill, requesting one row's decoration schedules only
    that row's load (the lazy `data()` path still exists via fill_mode=False)."""
    model = _make_model(fill_mode=False)
    model.set_paths([f"/p/{i:04d}.png" for i in range(100)])

    _ = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
    assert model._loading == {"/p/0000.png"}

    _ = model.data(model.index(5, 0), Qt.ItemDataRole.DecorationRole)
    assert model._loading == {"/p/0000.png", "/p/0005.png"}


def test_default_model_warms_the_full_directory():
    model = VirtualGalleryModel(worker_factory=_FakeLoaderWorker)
    model.set_paths(["/a.png", "/b.png"])
    model.fill()  # trigger fill after set_paths (visible-first protocol)
    assert model._loading == {"/a.png", "/b.png"}


def test_set_paths_eagerly_fills_all_rows():
    """fill() after set_paths pre-loads every row (no scroll / decoration
    request needed) so images are cached before the user scrolls."""
    model = _make_model()  # fill_mode=True by default
    model.set_paths([f"/p/{i:04d}.png" for i in range(20)])
    model.fill()  # trigger fill after set_paths (visible-first protocol)

    # No data()/prefetch call: the whole list is queued for loading.
    assert model._loading == {f"/p/{i:04d}.png" for i in range(20)}

    # Chained dispatch advances one round per event-loop turn; pump until the
    # fill queue drains (loading set empty AND no workers left in flight).
    for _ in range(60):
        _pump(model)
        if not model._loading and not model._active_workers:
            break
    assert len(model._cache) == 20
    assert model._loading == set()
    assert model._active_workers == set()


def test_visible_first_dispatch_first_worker_in_visible_range():
    """Regression: the first dispatched workers must cover visible-row paths
    (issue #522 blocking fix).  Without the fix, set_paths() triggered
    _fill_all() before the view reported its visible range, so the first
    workers were file-order offscreen paths."""
    paths = [f"/p/{i:04d}.png" for i in range(200)]
    model = VirtualGalleryModel(
        worker_factory=_FakeLoaderWorker
    )
    model.set_paths(paths)
    # Simulate the view reporting that rows 50-60 are visible.
    model.set_visible_range(50, 60)
    model.fill()

    # The first dispatched workers must be from the visible range [50..60].
    visible_paths = set(paths[50:61])
    active_paths = {w.path for w in model._active_workers}
    assert active_paths <= visible_paths, (
        f"Offscreen workers dispatched before visible: "
        f"{active_paths - visible_paths}"
    )


def test_loaded_thumbnail_lands_in_cache_and_emits_data_changed():
    model = _make_model()
    model.set_paths(["/a.png"])
    changes = []
    model.dataChanged.connect(
        lambda tl, br, roles: changes.append((tl.row(), br.row(), list(roles)))
    )

    icon_before = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
    assert "/a.png" not in model._cache

    _pump(model)

    assert "/a.png" in model._cache
    assert model._loading == set()
    assert changes == [(0, 0, [Qt.ItemDataRole.DecorationRole])]

    icon_after = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
    assert not icon_after.isNull()
    assert icon_before  # placeholder was a valid (transparent) icon too


def test_failed_load_lands_in_failed_and_is_not_retried():
    model = _make_model()
    model.set_paths(["/bad.png"])
    _FAIL_PATHS.add("/bad.png")
    try:
        _ = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
        _pump(model)
        assert "/bad.png" in model._failed
        assert "/bad.png" not in model._cache
        # A second decoration request must not re-schedule the failed path.
        _ = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
        assert model._loading == set()
    finally:
        _FAIL_PATHS.clear()


# --- Stale-load rejection ----------------------------------------------------


def test_stale_load_rejected_after_reset():
    model = _make_model(fill_mode=False)
    model.set_paths(["/a.png"])
    # Arm the hold BEFORE submitting the worker: otherwise a fast pool can
    # run it to completion before _STARTED.clear(), and the wait() below
    # then blocks on a worker that already finished.
    _BLOCK.set()
    _STARTED.clear()
    try:
        _ = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
        assert _STARTED.wait(2.0), "fake worker never started"
        model.set_paths(["/b.png"])  # bumps generation; /a.png result is stale
        _BLOCK.clear()
        _pump(model)
        assert "/a.png" not in model._cache
        assert "/b.png" not in model._cache  # never requested in the new list
        assert model._loading == set()
        assert model._active_workers == set()
    finally:
        _BLOCK.clear()


def test_cancel_loading_rejects_inflight():
    model = _make_model()
    model.set_paths(["/a.png", "/b.png"])
    # Arm the hold before submitting the workers (see test_stale_load_*).
    _BLOCK.set()
    _STARTED.clear()
    try:
        _ = model.data(model.index(0, 0), Qt.ItemDataRole.DecorationRole)
        _ = model.data(model.index(1, 0), Qt.ItemDataRole.DecorationRole)
        assert _STARTED.wait(2.0), "fake worker never started"
        model.cancel_loading()
        _BLOCK.clear()
        _pump(model)
        assert "/a.png" not in model._cache
        assert "/b.png" not in model._cache
        assert model._loading == set()
        assert model._active_workers == set()
    finally:
        _BLOCK.clear()


# --- View: selection, prefetch, sizing, signals -----------------------------


def test_selection_model_backs_gallery_selection():
    view = VirtualGalleryView()
    model = _make_model()
    view.setModel(model)
    model.set_paths([f"/p/{i}.png" for i in range(10)])
    view.show()
    QApplication.processEvents()

    sm = view.selectionModel()
    sm.select(model.index(2, 0), sm.SelectionFlag.Select)
    assert view.selected_paths() == ["/p/2.png"]

    view.select_all()
    assert set(view.selected_paths()) == {f"/p/{i}.png" for i in range(10)}

    view.clear_selection()
    assert view.selected_paths() == []
    view.close()


def test_scroll_prefetch_schedules_exact_visible_buffered_range():
    view = VirtualGalleryView()
    model = _make_model(fill_mode=False)
    view.setModel(model)
    paths = [f"/p/{i:04d}.png" for i in range(500)]
    model.set_paths(paths)
    view.resize(520, 320)
    view.show()
    QApplication.processEvents()

    view._prefetch_visible()
    lo, hi = view._visible_row_range(view._prefetch_buffer)
    assert lo >= 0 and hi > lo
    assert model._loading == set(paths[lo : hi + 1])
    # Widget/paint work stays tiny regardless of the 500-row backing list.
    assert (hi - lo + 1) < 200
    view.close()


def test_icon_rows_wrap_downward_and_every_item_is_vertically_reachable():
    view = VirtualGalleryView()
    model = _make_model(fill_mode=False)
    view.setModel(model)
    model.set_paths([f"/p/{i:04d}.png" for i in range(82)])
    view.resize(520, 320)
    view.show()
    QApplication.processEvents()

    assert view.flow() == view.Flow.LeftToRight
    assert view.verticalScrollBar().maximum() > 0
    assert view.horizontalScrollBar().maximum() == 0
    assert view.jump_to_path("/p/0081.png") is True
    QApplication.processEvents()
    assert view.visualRect(model.index(81, 0)).intersects(view.viewport().rect())
    view.close()


def test_set_thumbnail_size_updates_grid_and_emits_layout_changed():
    view = VirtualGalleryView()
    model = _make_model()
    view.setModel(model)
    model.set_paths(["/a.png"])
    view.resize(520, 320)

    layout_changed = []
    model.layoutChanged.connect(lambda *_: layout_changed.append(1))

    view.set_thumbnail_size(64)
    assert model.thumbnail_size == 64
    assert view.thumbnail_size() == 64
    assert view.iconSize().width() == 64
    assert layout_changed


def test_path_and_zoom_signals():
    view = VirtualGalleryView()
    model = _make_model()
    view.setModel(model)
    model.set_paths(["/a.png", "/b.png"])
    view.resize(400, 300)
    view.show()
    QApplication.processEvents()

    clicked, activated, right, zoom = [], [], [], []
    view.path_clicked.connect(clicked.append)
    view.path_activated.connect(activated.append)
    view.path_right_clicked.connect(lambda pos, p: right.append((pos, p)))
    view.ctrl_wheel.connect(zoom.append)

    view._on_pressed(model.index(0, 0))
    view._on_double_clicked(model.index(1, 0))

    rect = view.visualRect(model.index(0, 0))
    assert rect.isValid()
    view._on_context_menu(rect.center())
    assert clicked == ["/a.png"]
    assert activated == ["/b.png"]
    assert right and right[0][1] == "/a.png"
    assert right[0][0].x() >= 0

    view.ctrl_wheel.emit(120)
    assert zoom == [120]
    view.close()


# --- Drag-to-drop: native fallback plus wheel-aware Wallpaper path -----------


def test_start_drag_fires_a_qdrag_with_the_selected_file_urls(monkeypatch):
    from PySide6.QtGui import QDrag

    captured = {}

    def _fake_exec(self, *_a, **_kw):
        md = self.mimeData()
        captured["urls"] = [u.toLocalFile() for u in md.urls()] if md else []
        return Qt.DropAction.IgnoreAction

    monkeypatch.setattr(QDrag, "exec", _fake_exec, raising=False)

    view = VirtualGalleryView()
    model = _make_model()
    view.setModel(model)
    model.set_paths(["/a.png", "/b.png"])
    view.set_custom_drag_enabled(True)
    view.resize(400, 300)
    view.show()
    QApplication.processEvents()

    view._drag_source_path = "/a.png"
    view._drag_press_pos = QPoint(1, 1)
    view._start_custom_drag()

    assert captured["urls"] == ["/a.png"]
    # No mouse grab was ever taken, and the transient press state is cleared.
    assert QWidget.mouseGrabber() is None
    assert view._drag_source_path is None
    assert view._drag_press_pos is None
    view.close()


def test_start_drag_with_no_source_is_a_noop(monkeypatch):
    from PySide6.QtGui import QDrag

    calls = []
    monkeypatch.setattr(QDrag, "exec", lambda self, *a, **k: calls.append(1), raising=False)

    view = VirtualGalleryView()
    model = _make_model()
    view.setModel(model)
    model.set_paths(["/a.png"])
    view.set_custom_drag_enabled(True)

    view._drag_source_path = None
    view._start_custom_drag()

    assert calls == []
    assert QWidget.mouseGrabber() is None
    view.close()


def test_manual_wallpaper_drag_wheel_scrolls_outer_page(q_app):
    from PySide6.QtWidgets import QScrollArea, QVBoxLayout

    owner = QWidget()
    owner.main_scroll_area = QScrollArea(owner)
    content = QWidget()
    content.setMinimumHeight(1800)
    owner.main_scroll_area.setWidget(content)
    owner.main_scroll_area.setWidgetResizable(True)
    layout = QVBoxLayout(owner)
    layout.addWidget(owner.main_scroll_area)

    view = VirtualGalleryView(content)
    model = _make_model(fill_mode=False)
    view.setModel(model)
    model.set_paths(["/a.png"])
    drops = []
    view.set_custom_drag_enabled(
        True, lambda source, paths, pos: drops.append((source, paths, pos))
    )
    owner.resize(400, 300)
    owner.show()
    QApplication.processEvents()

    bar = owner.main_scroll_area.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(bar.maximum() // 2)
    before = bar.value()
    view._drag_source_path = "/a.png"
    view._drag_press_pos = QPoint(1, 1)
    view._start_custom_drag()

    assert view._manual_drag_active is True
    wheel = QWheelEvent(
        QPointF(20, 20),
        QPointF(20, 20),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    assert view.eventFilter(view, wheel) is True
    assert bar.value() > before
    view._end_manual_drag(drop=True, global_pos=QPoint(20, 20))
    assert drops == [("/a.png", ["/a.png"], QPoint(20, 20))]
    assert view._manual_drag_active is False
    owner.close()


def _mouse_event(kind, pos, *, button, buttons):
    from PySide6.QtGui import QMouseEvent

    p = QPointF(pos)
    return QMouseEvent(
        kind, p, p, button, buttons, Qt.KeyboardModifier.NoModifier
    )


def _wallpaper_view(q_app, n_paths=3):
    from PySide6.QtWidgets import QScrollArea, QVBoxLayout

    owner = QWidget()
    owner.main_scroll_area = QScrollArea(owner)
    content = QWidget()
    owner.main_scroll_area.setWidget(content)
    owner.main_scroll_area.setWidgetResizable(True)
    QVBoxLayout(owner).addWidget(owner.main_scroll_area)

    view = VirtualGalleryView(content)
    model = _make_model(fill_mode=False)
    view.setModel(model)
    model.set_paths([f"/p/{i}.png" for i in range(n_paths)])
    view.set_custom_drag_enabled(True, lambda *a: None)
    owner.resize(500, 360)
    owner.show()
    QApplication.processEvents()
    return owner, view, model


def test_press_on_thumbnail_then_drag_never_starts_a_marquee(q_app):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QAbstractItemView

    owner, view, model = _wallpaper_view(q_app)
    item_pos = view.visualRect(model.index(0, 0)).center()
    assert view.indexAt(item_pos).isValid()

    view.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress, item_pos,
            button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton,
        )
    )
    # Sub-threshold move: must be swallowed, no rubber band.
    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove, item_pos + QPoint(3, 2),
            button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.LeftButton,
        )
    )
    assert view.state() != QAbstractItemView.State.DragSelectingState

    # Past-threshold move: starts the in-app drag, still no rubber band.
    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove, item_pos + QPoint(40, 40),
            button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.LeftButton,
        )
    )
    assert view._manual_drag_active is True
    assert view.state() != QAbstractItemView.State.DragSelectingState

    view._end_manual_drag(drop=False)
    owner.close()


def test_press_on_blank_space_still_marquees(q_app):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QAbstractItemView

    owner, view, model = _wallpaper_view(q_app, n_paths=2)
    blank = QPoint(view.viewport().width() - 6, view.viewport().height() - 6)
    assert not view.indexAt(blank).isValid()

    view.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress, blank,
            button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton,
        )
    )
    assert view._drag_source_path is None
    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove, blank - QPoint(60, 60),
            button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.LeftButton,
        )
    )
    assert view.state() == QAbstractItemView.State.DragSelectingState
    owner.close()


def test_stale_drag_source_from_prior_click_does_not_block_marquee(q_app):
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QAbstractItemView

    owner, view, model = _wallpaper_view(q_app, n_paths=2)
    item_pos = view.visualRect(model.index(0, 0)).center()

    # Click an item without dragging, then release.
    view.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress, item_pos,
            button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton,
        )
    )
    view.mouseReleaseEvent(
        _mouse_event(
            QEvent.Type.MouseButtonRelease, item_pos,
            button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.NoButton,
        )
    )
    assert view._drag_source_path is None

    # A subsequent blank-space drag must marquee, not resurrect the drag.
    blank = QPoint(view.viewport().width() - 6, view.viewport().height() - 6)
    view.mousePressEvent(
        _mouse_event(
            QEvent.Type.MouseButtonPress, blank,
            button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton,
        )
    )
    view.mouseMoveEvent(
        _mouse_event(
            QEvent.Type.MouseMove, blank - QPoint(60, 60),
            button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.LeftButton,
        )
    )
    assert view._manual_drag_active is False
    assert view.state() == QAbstractItemView.State.DragSelectingState
    owner.close()


def test_drag_preview_window_is_transparent_to_clicks():
    """Purely a visual overlay; must never be able to eat a click even if a
    bug elsewhere leaves it on screen after its drag ends."""
    from gui.src.windows.drag_preview_window import DragPreviewWindow
    from PySide6.QtGui import QPixmap

    preview = DragPreviewWindow(QPixmap())
    assert preview.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    preview.close()


# --- Composite widget API ----------------------------------------------------


def test_composite_widget_api():
    gallery = VirtualGallery()
    paths = [f"/p/{i:04d}.png" for i in range(50)]
    gallery.set_paths(paths)
    assert gallery.count() == 50
    assert gallery.thumbnail_size == 180

    gallery.set_thumbnail_size(96)
    assert gallery.thumbnail_size == 96
    assert gallery.view.iconSize().width() == 96

    assert gallery.selected_files() == []
    selection_events = []
    gallery.selection_changed.connect(lambda *_: selection_events.append(1))
    gallery.select_all()
    assert len(gallery.selected_files()) == 50
    assert selection_events
    gallery.clear_selection()
    assert gallery.selected_files() == []

    assert gallery.jump_to_path("/p/0025.png") is True
    assert gallery.jump_to_path("/missing.png") is False

    gallery.clear()
    assert gallery.count() == 0
    gallery.clear_cache()
    gallery.cancel_loading()


def test_composite_forwards_view_signals():
    gallery = VirtualGallery()
    gallery.set_paths(["/a.png", "/b.png"])
    gallery.show()
    QApplication.processEvents()

    clicked, activated, zoom = [], [], []
    gallery.path_clicked.connect(clicked.append)
    gallery.path_activated.connect(activated.append)
    gallery.ctrl_wheel.connect(zoom.append)

    gallery.view._on_pressed(gallery.model.index(0, 0))
    gallery.view._on_double_clicked(gallery.model.index(1, 0))
    gallery.view.ctrl_wheel.emit(120)
    assert clicked == ["/a.png"]
    assert activated == ["/b.png"]
    assert zoom == [120]
    gallery.close()


# --- Dual-gallery selected / preview marks ------------------------------------


def test_dual_gallery_syncs_selected_marks_and_preview():
    dual = VirtualDualGallery(worker_factory=_FakeLoaderWorker)
    dual.set_found_paths(["/a.png", "/b.png", "/c.png"])

    dual.set_selected_paths(["/a.png"])
    assert dual.found_gallery.model.is_selected("/a.png") is True
    assert dual.found_gallery.model.is_selected("/b.png") is False
    assert dual.selected_gallery.model.is_selected("/a.png") is True

    dual.toggle_selection("/b.png")
    assert dual.found_gallery.model.is_selected("/b.png") is True
    assert dual.count_selected() == 2

    dual.deselect_all()
    assert dual.found_gallery.model.is_selected("/a.png") is False
    assert dual.found_gallery.model.is_selected("/b.png") is False
    assert dual.selected_gallery.model.is_selected("/a.png") is False

    dual.set_preview(["/c.png"])
    assert dual.found_gallery.model.is_preview("/c.png") is True
    assert dual.selected_gallery.model.is_preview("/c.png") is True
    dual.mark_preview("/c.png", False)
    assert dual.found_gallery.model.is_preview("/c.png") is False
    dual.close()


def test_dual_gallery_selected_marks_survive_found_refresh():
    dual = VirtualDualGallery(worker_factory=_FakeLoaderWorker)
    dual.set_found_paths(["/a.png", "/b.png"])
    dual.set_selected_paths(["/b.png"])
    # A found-panel refresh re-applies the selection marks to the new rows.
    dual.set_found_paths(["/a.png", "/b.png", "/c.png"])
    assert dual.found_gallery.model.is_selected("/b.png") is True
    dual.close()
