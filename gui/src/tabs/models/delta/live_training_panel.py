"""Live training panel: epoch bar, sparkline, scrubbable loss curve, filmstrip (#742).

``TrainingEventTail`` delivers events off the GUI thread. Thumbnail bytes
are scaled on a worker before a button icon is set. The compare pane is
an embedded ``ImageCompareWindow``, not a second canvas.
"""
from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from pathlib import Path

from backend.src.core.training_curve import (
    bucket_minmax,
    checkpoint_index,
    latest_epoch,
    loss_series,
    sample_file,
    smooth_series,
    step_at_ratio,
)
from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.src.helpers.models.training_event_tail import TrainingEventTail
from gui.src.tabs.models.delta.cbir_train_tab._sparkline import _SparkLine
from gui.src.windows.image_compare_window import ImageCompareWindow

_THUMB = 72
_MAX_PIXELS = 16_000_000
_PENDING_CAP = 200


@dataclass
class _Shot:
    step: int
    path: Path


class LossCurve(QWidget):
    """Min/max buckets plus a smoothed guide. Mouse x maps onto a raw step."""

    step_hovered = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("live_training_curve")
        self.setMinimumHeight(120)
        self.setMouseTracking(True)
        self._points: list[tuple[int, float]] = []
        self._smooth: list[tuple[int, float]] = []
        self._cursor: int | None = None

    def set_points(self, points: list[tuple[int, float]]) -> None:
        self._points = list(points)
        self._smooth = smooth_series(self._points)
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._points:
            return
        width = max(1, self.width() - 1)
        ratio = min(1.0, max(0.0, event.position().x() / width))
        step = step_at_ratio(self._points, ratio)
        if step is None:
            return
        self._cursor = step
        self.step_hovered.emit(step)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#1e1e1e"))
        if not self._points:
            painter.setPen(QColor("#9a9a9a"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Loss curve")
            painter.end()
            return
        buckets = bucket_minmax(self._points, max(1, self.width() // 4))
        lo, hi = _span(buckets)
        painter.setPen(QPen(QColor("#5b8def"), 2))
        for _first, last, low, high in buckets:
            x = _x_for(self._points, last, self.width())
            painter.drawLine(x, _y(high, lo, hi, self.height()), x, _y(low, lo, hi, self.height()))
        _draw_smooth(painter, self._points, self._smooth, lo, hi, self.width(), self.height())
        if self._cursor is not None:
            painter.setPen(QPen(QColor("#f2c14e"), 1))
            x = _x_for(self._points, self._cursor, self.width())
            painter.drawLine(x, 0, x, self.height())
        painter.end()


def _span(buckets: list[tuple[int, int, float, float]]) -> tuple[float, float]:
    lows = [item[2] for item in buckets]
    highs = [item[3] for item in buckets]
    lo, hi = min(lows), max(highs)
    if hi == lo:
        hi = lo + 1.0
    return lo, hi


def _y(value: float, lo: float, hi: float, height: int) -> int:
    return int((1.0 - (value - lo) / (hi - lo)) * max(1, height - 1))


def _x_for(points: list[tuple[int, float]], step: int, width: int) -> int:
    if len(points) < 2:
        return 0
    first, last = points[0][0], points[-1][0]
    if last == first:
        return 0
    ratio = (step - first) / (last - first)
    return int(min(1.0, max(0.0, ratio)) * max(1, width - 1))


def _draw_smooth(painter, points, smooth, lo, hi, width, height) -> None:
    if len(smooth) < 2:
        return
    painter.setPen(QPen(QColor("#e8e8e8"), 2))
    # A 10k-step run is normal. The guide is a summary, not one segment per point.
    stride = max(1, len(smooth) // max(1, width // 4))
    sampled = smooth[::stride]
    if sampled[-1] != smooth[-1]:
        sampled.append(smooth[-1])
    previous = None
    for step, loss in sampled:
        point = (_x_for(points, step, width), _y(loss, lo, hi, height))
        if previous is not None:
            painter.drawLine(previous[0], previous[1], point[0], point[1])
        previous = point


class LiveTrainingPanel(QWidget):
    """Epoch progress, the last 64 losses, the full curve, and checkpoint samples."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("live_training_panel")
        self._events: list[dict] = []
        self._shots: list[_Shot] = []
        self._known: set[int] = set()
        self._highlight: int | None = None
        self._run_dir: Path | None = None
        self._compare: ImageCompareWindow | None = None
        self._jobs: queue.Queue = queue.Queue()
        self._pending: set[int] = set()
        self._generation = 0
        self._worker: threading.Thread | None = None
        self._tail = TrainingEventTail(self)
        self._tail.events.connect(self.ingest)
        self._thumbs = _ThumbBus()
        self._thumbs.ready.connect(self._apply_thumb)
        self.destroyed.connect(lambda *_args: self.shutdown())
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 8, 0, 0)
        self._epoch = QProgressBar()
        self._epoch.setObjectName("live_training_epoch")
        self._epoch.setRange(0, 1)
        self._epoch.setValue(0)
        self._epoch.setFormat("Epoch %v / %m")
        root.addWidget(self._epoch)
        self._spark = _SparkLine("loss")
        self._spark.setObjectName("live_training_sparkline")
        root.addWidget(self._spark)
        self._curve = LossCurve()
        self._curve.step_hovered.connect(self.highlight_step)
        root.addWidget(self._curve)
        self._strip_host = QWidget()
        self._strip = QHBoxLayout(self._strip_host)
        self._strip.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("live_training_filmstrip")
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._strip_host)
        scroll.setMinimumHeight(_THUMB + 36)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        root.addWidget(scroll)
        self._compare_host = QVBoxLayout()
        root.addLayout(self._compare_host)
        note = QLabel("Scrub the curve to highlight the latest checkpoint at or before that step.")
        note.setWordWrap(True)
        root.addWidget(note)

    def begin(self, epoch_budget: int) -> None:
        """Clear the panel for a new run and set the determinate epoch budget."""
        self.shutdown()
        self._events.clear()
        self._shots.clear()
        self._known.clear()
        self._pending.clear()
        self._highlight = None
        self._run_dir = None
        self._spark.reset()
        self._curve.set_points([])
        self._epoch.setRange(0, max(1, int(epoch_budget)))
        self._epoch.setValue(0)
        self._clear_strip()
        self._set_compare([])

    def follow(self, run_dir: str) -> None:
        self._run_dir = Path(run_dir)
        self._tail.start(self._run_dir)

    def shutdown(self) -> None:
        self._generation += 1
        self._tail.stop()

    def ingest(self, events: list) -> None:
        if not events:
            return
        self._events.extend(event for event in events if isinstance(event, dict))
        points = loss_series(self._events)
        self._curve.set_points(points)
        self._spark.reset()
        for _step, loss in points[-_SparkLine.MAX_POINTS :]:
            self._spark.push(loss)
        epoch = latest_epoch(self._events)
        if epoch is not None:
            if epoch > self._epoch.maximum():
                self._epoch.setMaximum(epoch)
            self._epoch.setValue(min(epoch, self._epoch.maximum()))
        for event in events:
            self._note_sample(event)

    def highlight_step(self, step: int) -> None:
        index = checkpoint_index([shot.step for shot in self._shots], step)
        if index is None or index == self._highlight:
            return
        self._highlight = index
        self._mark_buttons()
        self._show_compare(index)

    def _note_sample(self, event: dict) -> None:
        if self._run_dir is None or not isinstance(event, dict):
            return
        relative = event.get("sample")
        if not isinstance(relative, str):
            return
        step = event.get("step")
        if isinstance(step, bool) or not isinstance(step, int):
            return
        path = sample_file(self._run_dir, relative)
        if path is None or step in self._known:
            return
        self._known.add(step)
        self._shots.append(_Shot(step, path))
        self._shots.sort(key=lambda shot: shot.step)
        self._rebuild_strip()
        self._enqueue(step, path)

    def _rebuild_strip(self) -> None:
        self._clear_strip()
        for shot in self._shots:
            button = QPushButton(f"step {shot.step}")
            button.setObjectName(f"checkpoint_{shot.step}")
            button.setCheckable(True)
            button.setChecked(self._highlight is not None and self._shots[self._highlight].step == shot.step)
            button.clicked.connect(lambda _checked=False, value=shot.step: self.highlight_step(value))
            self._strip.addWidget(button)
        self._strip.addStretch()

    def _mark_buttons(self) -> None:
        chosen = None if self._highlight is None else self._shots[self._highlight].step
        for shot in self._shots:
            button = self.findChild(QPushButton, f"checkpoint_{shot.step}")
            if button is not None:
                button.setChecked(shot.step == chosen)

    def _show_compare(self, index: int) -> None:
        paths = []
        if index > 0:
            paths.append(str(self._shots[index - 1].path))
        paths.append(str(self._shots[index].path))
        self._set_compare(paths)

    def _set_compare(self, paths: list[str]) -> None:
        if self._compare is not None:
            self._compare.setParent(None)
            self._compare.deleteLater()
            self._compare = None
        if not paths:
            return
        self._compare = ImageCompareWindow(paths, embedded=True)
        self._compare.setObjectName("live_training_compare")
        self._compare_host.addWidget(self._compare)

    def _clear_strip(self) -> None:
        while self._strip.count():
            item = self._strip.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _enqueue(self, step: int, path: Path) -> None:
        if step in self._pending or len(self._pending) >= _PENDING_CAP:
            return
        self._pending.add(step)
        self._jobs.put((step, path))
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._pump, name="training-thumbs", daemon=True)
            self._worker.start()

    def _pump(self) -> None:
        generation = self._generation
        while generation == self._generation:
            try:
                step, path = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            self._pending.discard(step)
            if generation != self._generation:
                return
            data = _scaled_png(path)
            if data and generation == self._generation:
                self._thumbs.ready.emit(step, data)

    def _apply_thumb(self, step: int, data: bytes) -> None:
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        button = self.findChild(QPushButton, f"checkpoint_{step}")
        if button is not None:
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(_THUMB, _THUMB))


class _ThumbBus(QWidget):
    """Qt signal owner so thumbnail bytes hop back to the GUI thread."""

    ready = Signal(int, bytes)


def _scaled_png(path: Path) -> bytes | None:
    image = QImage(str(path))
    if image.isNull():
        return None
    if image.width() * image.height() > _MAX_PIXELS:
        return None
    scaled = image.scaled(
        _THUMB, _THUMB, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    store = QBuffer()
    store.open(QIODevice.OpenModeFlag.WriteOnly)
    if not scaled.save(store, "PNG"):
        return None
    return bytes(store.data())
