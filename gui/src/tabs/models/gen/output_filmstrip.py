"""Generate surface output filmstrip and thumbnail decoding (split from generate_surface)."""

from __future__ import annotations

import contextlib
import inspect
import queue
import threading

from backend.src.comfy_matrix import (
    output_paths,
)
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _scroll(name: str, horizontal: bool) -> tuple[QScrollArea, QWidget, QHBoxLayout | QVBoxLayout]:
    host = QWidget()
    layout = QHBoxLayout(host) if horizontal else QVBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    scroll = QScrollArea()
    scroll.setObjectName(name)
    scroll.setWidgetResizable(True)
    scroll.setWidget(host)
    if horizontal:
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(120)
    else:
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumHeight(140)
    return scroll, host, layout


class OutputFilmstrip(QWidget):
    """Scrollable strip and matrix grid. Thumbnails load off the GUI thread."""

    thumb_ready = Signal(str, object)
    _KEEP = 200

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("generate_filmstrip")
        self._records: dict[str, object] = {}
        self._order: list[str] = []
        self._selected_id: str | None = None
        self._thumbs: dict[str, QPixmap] = {}
        self._pending: set[str] = set()
        self._fetcher = None
        self._jobs: queue.Queue = queue.Queue(maxsize=self._KEEP)
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self.thumb_ready.connect(self._apply_thumb)
        self.destroyed.connect(lambda *_args, stop=self._stop: stop.set())
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        strip_scroll, _strip_host, self._strip = _scroll("generate_filmstrip_scroll", True)
        grid_scroll, _grid_host, self._grids = _scroll("generate_matrix_scroll", False)
        root.addWidget(strip_scroll)
        root.addWidget(grid_scroll)

    def set_view_fetcher(self, fetcher) -> None:
        """``fetcher(filename, subfolder, kind) -> bytes`` runs on a worker thread."""
        self._fetcher = fetcher

    def upsert(self, record) -> None:
        prompt_id = getattr(record, "prompt_id", None)
        if not isinstance(prompt_id, str):
            return
        if prompt_id not in self._records:
            self._order.append(prompt_id)
        self._records[prompt_id] = record
        while len(self._order) > self._KEEP:
            expired = self._order.pop(0)
            self._records.pop(expired, None)
            self._thumbs.pop(expired, None)
            self._pending.discard(expired)
            if self._selected_id == expired:
                self._selected_id = None
        self._enqueue(record)
        self._rebuild()

    def selected_record(self):
        if self._selected_id is None:
            return None
        return self._records.get(self._selected_id)

    def select(self, prompt_id: str) -> None:
        if prompt_id in self._records:
            self._choose(prompt_id)

    def _choose(self, prompt_id: str) -> None:
        self._selected_id = prompt_id
        self._rebuild()

    def _rebuild(self) -> None:
        _clear_layout(self._strip)
        _clear_layout(self._grids)
        groups: dict[str, list] = {}
        for prompt_id in self._order:
            record = self._records[prompt_id]
            if getattr(record, "surface_mode", None) == "matrix":
                parent = getattr(record, "parent_prompt_id", None)
                key = parent if isinstance(parent, str) and parent else prompt_id
                groups.setdefault(key, []).append(record)
            else:
                self._strip.addWidget(self._cell(record))
        self._strip.addStretch()
        for key, records in groups.items():
            self._grids.addWidget(self._grid(key, records))

    def _enqueue(self, record) -> None:
        prompt_id = record.prompt_id
        if prompt_id in self._thumbs or prompt_id in self._pending:
            return
        local = getattr(record, "local_output_path", None)
        if isinstance(local, str) and local:
            job = ("local", prompt_id, local)
        else:
            if self._fetcher is None:
                return
            filename, subfolder, kind = _first_output(record)
            if not filename:
                return
            job = ("remote", prompt_id, filename, subfolder, kind)
        self._pending.add(prompt_id)
        self._ensure_worker()
        try:
            self._jobs.put_nowait(job)
        except queue.Full:
            with contextlib.suppress(queue.Empty):
                _tag, expired, *_ = self._jobs.get_nowait()
                self._pending.discard(expired)
            self._jobs.put_nowait(job)

    def _ensure_worker(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._pump, name="filmstrip-thumbs", daemon=True)
        self._worker.start()

    def _pump(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._jobs.get(timeout=0.2)
            except queue.Empty:
                continue
            prompt_id = job[1]
            image = QImage()
            if job[0] == "local":
                if prompt_id in self._records:
                    image = _decode_thumbnail_file(job[2])
            else:
                _tag, _pid, filename, subfolder, kind = job
                data = None
                fetcher = self._fetcher
                if fetcher is not None and prompt_id in self._records:
                    try:
                        data = fetcher(filename, subfolder, kind)
                    except Exception:
                        data = None
                if isinstance(data, (bytes, bytearray)) and data:
                    image = _decode_thumbnail(bytes(data))
            self._pending.discard(prompt_id)
            if not image.isNull() and not self._stop.is_set():
                try:
                    self.thumb_ready.emit(prompt_id, image)
                except RuntimeError:
                    return  # View destroyed while the fetch was in flight.

    def _apply_thumb(self, prompt_id: str, image: QImage) -> None:
        if prompt_id not in self._records or image.isNull():
            return
        pixmap = QPixmap.fromImage(image)
        self._thumbs[prompt_id] = pixmap
        while len(self._thumbs) > self._KEEP:
            self._thumbs.pop(next(iter(self._thumbs)), None)
        button = self.findChild(QPushButton, f"filmstrip_{prompt_id}")
        if button is not None:
            _set_thumb(button, pixmap)

    def _cell(self, record) -> QPushButton:
        prompt_id = record.prompt_id
        button = QPushButton(_cell_text(record))
        button.setCheckable(True)
        button.setChecked(prompt_id == self._selected_id)
        button.setObjectName(f"filmstrip_{prompt_id}")
        thumb = self._thumbs.get(prompt_id)
        if thumb is not None:
            _set_thumb(button, thumb)
        button.clicked.connect(lambda _=False, pid=prompt_id: self._choose(pid))
        return button

    def _grid(self, key: str, records: list) -> QWidget:
        host = QWidget()
        host.setObjectName(f"matrix_grid_{key}")
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel(f"Sweep {key}"))
        for record in records:
            row.addWidget(self._cell(record))
        row.addStretch()
        return host


def _decode_thumbnail_file(path: str) -> QImage:
    """72px thumbnail decoded from a local file without a full-res read.

    Server-fetched bytes go through :func:`_decode_thumbnail` (2MB cap);
    upscaled 4x files routinely exceed that, so local records decode via
    ``QImageReader`` scaling instead. Returns null on any failure.
    """
    try:
        reader = QImageReader(path)
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > 64_000_000:
            return QImage()
        reader.setScaledSize(size.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
    except Exception:
        return QImage()
    if image.isNull():
        return image
    return image.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation)


def _cell_text(record) -> str:
    paths = output_paths(record)
    if not paths:
        local = getattr(record, "local_output_path", None)
        if isinstance(local, str) and local:
            paths = (local,)
    path = paths[0] if paths else "no output"
    status = getattr(record, "status", "")
    mode = getattr(record, "surface_mode", None) or ""
    axis = getattr(record, "sweep_axis", None)
    extra = f" {axis}={record.sweep_value}" if axis else ""
    variant = getattr(record, "variant_label", None)
    tag = f" [{variant}]" if isinstance(variant, str) and variant else ""
    return f"{record.prompt_id} {status}{extra} {path} {mode}{tag}".strip()


def _first_output(record) -> tuple[str, str, str]:
    for item in getattr(record, "outputs", ()) or ():
        filename = getattr(item, "filename", None)
        if isinstance(filename, str) and filename:
            subfolder = getattr(item, "subfolder", "") or ""
            return filename, subfolder if isinstance(subfolder, str) else "", getattr(item, "type", "output")
    return "", "", "output"


def _decode_thumbnail(data: bytes) -> QImage:
    if len(data) > 2_000_000:
        return QImage()
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    reader = QImageReader(buffer)
    size = reader.size()
    if not size.isValid() or size.width() * size.height() > 16_000_000:
        return QImage()
    reader.setScaledSize(size.scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio))
    return reader.read().scaled(72, 72, Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation)


def _set_thumb(button: QPushButton, pixmap: QPixmap) -> None:
    button.setIcon(QIcon(pixmap))
    button.setIconSize(QSize(72, 72))


def _manager_view_fetcher(manager):
    method = getattr(type(manager), "fetch_view", None)
    if not inspect.isfunction(method):
        return None

    def fetch(filename: str, subfolder: str, kind: str):
        try:
            return method(manager, filename, subfolder, kind)
        except Exception:
            return None

    return fetch
