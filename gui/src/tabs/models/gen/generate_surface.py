"""Unified Generate surface: Guided | Graph, shared filmstrip, matrix sweeps.

External-only (#729): Graph does not create a WebEngine view. The canvas
is the system browser. A local JSON draft is kept across mode switches
and is never replaced while it has unsaved edits (#739). Matrix mode
queues one existing ``queue_workflow`` per cell on one GPU lease (#740).
"""
from __future__ import annotations

import contextlib
import inspect
import json
import os
import queue
import threading
from dataclasses import dataclass
from types import SimpleNamespace

from backend.src.comfy_matrix import (
    AXES,
    AxisNotInWorkflow,
    UnknownWorkflowNodeError,
    build_promoted_submission,
    find_node_id,
    gpu_lease,
    output_paths,
    parse_graph_submission,
    prepare_sweep,
    run_matrix_sweep,
    try_admit,
)
from backend.src.constants import LOCAL_SOURCE_PATH
from backend.src.constants.comfy import ServerState
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.tabs.models.gen.comfy_generate_tab import (
    WORKFLOW_MODES,
    ComfyUITab,
    plan_guided_workflow,
)
from gui.src.tabs.models.upscale_handoff import UpscaleRunner

_MODES = ("guided", "graph", "matrix")


def _template_issue(manager, workflow) -> str | None:
    """None means fail-open (no cache) or no issues. Matches #738."""
    get_info = getattr(manager, "get_object_info", None)
    validate = getattr(manager, "validate_template", None)
    if not callable(get_info) or not callable(validate) or get_info() is None:
        return None
    try:
        issues = list(validate(workflow))
    except Exception:
        return None
    if not issues:
        return None
    return str(getattr(issues[0], "message", issues[0]))


def _sweep_status(result) -> str:
    count = len(result.prompt_ids)
    if result.stopped == "lease":
        holder = gpu_lease.owner or "another job"
        return f"GPU admission is held by {holder}."
    if result.stopped == "cap":
        return "Sweep exceeds the cell cap."
    if result.stopped == "thermal":
        return f"Stopped between cells under thermal pressure after {count} cell(s)."
    if result.stopped == "pressure":
        return f"Stopped between cells under VRAM pressure after {count} cell(s)."
    if result.stopped == "stop":
        return f"Stopped between cells after {count} cell(s)."
    if result.stopped == "execution":
        return f"Sweep stopped after {count} cell(s): execution failed or connection closed."
    return f"Completed {count} cells. Parent {result.parent_prompt_id}."


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


class GraphDraft(QWidget):
    """Local workflow JSON. Mode switches do not write this widget."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loaded = ""
        self.dirty = False
        self._applying = False
        layout = QVBoxLayout(self)
        note = QLabel(
            "External-only: the graph canvas is your system browser. "
            "This draft is kept when you switch modes, and unsaved edits are not overwritten."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("generate_graph_editor")
        self.editor.setPlaceholderText('{"1": {"class_type": "KSampler", "inputs": {}}}')
        self.editor.textChanged.connect(self._on_text)
        layout.addWidget(self.editor, stretch=1)
        override_row = QHBoxLayout()
        override_row.addWidget(QLabel("Node overrides:"))
        self.overrides = QLineEdit("{}")
        self.overrides.setObjectName("generate_graph_overrides")
        self.overrides.setPlaceholderText('{"999": {"seed": 1}}')
        override_row.addWidget(self.overrides, stretch=1)
        layout.addLayout(override_row)
        self.error = QLabel("")
        self.error.setWordWrap(True)
        self.error.setObjectName("generate_graph_error")
        layout.addWidget(self.error)

    def _on_text(self) -> None:
        if not self._applying:
            self.dirty = self.editor.toPlainText() != self._loaded

    def replace_text(self, text: str, *, force: bool = False) -> bool:
        if self.dirty and not force:
            self.error.setText("Unsaved graph edits were kept.")
            return False
        self._applying = True
        self.editor.setPlainText(text)
        self._applying = False
        self._loaded = text
        self.dirty = False
        self.error.setText("")
        return True

    def load_record(self, record) -> bool:
        workflow = getattr(record, "workflow", None)
        if not isinstance(workflow, dict):
            self.error.setText("Selected run has no workflow JSON.")
            return False
        return self.replace_text(json.dumps(workflow, indent=2))


@dataclass(frozen=True)
class MatrixJob:
    mode: str
    image_path: str
    base_checkpoint: str
    extra_checkpoint: str
    positive_prompt: str
    negative_prompt: str
    seed: int
    width: int
    height: int
    axis: str
    values: tuple
    workflow: dict | None = None
    template_name: str | None = None
    applied_overrides: dict | None = None


class GenerateSurface(QWidget):
    """Guided, Graph, and Matrix share one filmstrip and one run record feed."""

    _matrix_status = Signal(str)

    def __init__(self, enable_manager=False, controller=None, parent=None) -> None:
        super().__init__(parent)
        from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController

        self._controller = controller or ComfyWorkspaceController.instance()
        self._manager = self._controller.manager
        self._mode = "guided"
        self._sweep_stop = threading.Event()
        self.destroyed.connect(lambda *_args, event=self._sweep_stop: event.set())
        self.guided = ComfyUITab(enable_manager=enable_manager, controller=self._controller)
        self.graph = GraphDraft()
        self._filmstrip = OutputFilmstrip()
        self._view_fetch = _manager_view_fetcher(self._manager)
        if self._view_fetch is not None:
            self._filmstrip.set_view_fetcher(self._view_fetch)
        self._upscaler = UpscaleRunner(self)
        self._upscaler.finished.connect(self._on_upscale_finished)
        self._upscaler.error.connect(self._on_upscale_error)
        self._upscale_source_id: str | None = None
        self._build_ui()
        _attach_graph_actions(self)
        self._matrix_status.connect(self._matrix_message.setText)
        self._controller.run_record_changed.connect(self._filmstrip.upsert)
        self._load_existing_runs()
        self.set_mode("guided")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.addLayout(self._mode_row())
        upscale_row = QHBoxLayout()
        self._upscale_btn = QPushButton("Upscale selected")
        self._upscale_btn.setObjectName("generate_upscale_selected")
        self._upscale_btn.setToolTip("Upscale the filmstrip selection with Real-ESRGAN anime_6B (#749)")
        self._upscale_btn.clicked.connect(self._on_upscale_selected)
        self._upscale_message = QLabel("")
        self._upscale_message.setWordWrap(True)
        self._upscale_message.setObjectName("generate_upscale_status")
        upscale_row.addWidget(self._upscale_btn)
        upscale_row.addWidget(self._upscale_message, stretch=1)
        root.addLayout(upscale_row)
        root.addWidget(self._filmstrip)
        self._stack = QStackedWidget()
        self._stack.addWidget(self.guided)
        self._stack.addWidget(self.graph)
        self._stack.addWidget(self._matrix_page())
        root.addWidget(self._stack, stretch=1)

    def _mode_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._mode_buttons: dict[str, QPushButton] = {}
        for key, label in (("guided", "Guided"), ("graph", "Graph"), ("matrix", "Matrix")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName(f"generate_mode_{key}")
            button.clicked.connect(lambda _=False, mode=key: self.set_mode(mode))
            self._mode_buttons[key] = button
            row.addWidget(button)
        row.addStretch()
        return row

    def _matrix_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(
            "One axis, 3–9 values, shared in-process GPU admission. "
            "Cells queue through the existing workflow API at preview size. "
            "An axis stays disabled until this workflow has its node. "
            "Promote clones the selected cell at the guided size."
        ))
        self._use_graph = QCheckBox("Sweep the graph draft")
        self._use_graph.setObjectName("generate_matrix_use_graph")
        self._use_graph.toggled.connect(lambda _checked: self._sync_matrix_axes())
        layout.addWidget(self._use_graph)
        axis_row = QHBoxLayout()
        axis_row.addWidget(QLabel("Axis:"))
        self._axis = QComboBox()
        self._axis.setObjectName("generate_matrix_axis")
        for key, label in (
            ("seed", "Seed"),
            ("cfg", "CFG"),
            ("steps", "Steps"),
            ("lora_weight", "LoRA weight"),
            ("controlnet_strength", "ControlNet strength"),
        ):
            self._axis.addItem(label, key)
        self._axis.currentIndexChanged.connect(lambda _i: self._refresh_estimate())
        axis_row.addWidget(self._axis, stretch=1)
        layout.addLayout(axis_row)
        self._values = QLineEdit()
        self._values.setObjectName("generate_matrix_values")
        self._values.setPlaceholderText("0, 1, 2")
        self._values.textChanged.connect(lambda _t: self._refresh_estimate())
        layout.addWidget(self._values)
        self._matrix_message = QLabel("")
        self._matrix_message.setWordWrap(True)
        self._matrix_message.setObjectName("generate_matrix_message")
        layout.addWidget(self._matrix_message)
        buttons = QHBoxLayout()
        queue = QPushButton("Queue sweep")
        queue.setObjectName("generate_matrix_queue")
        queue.clicked.connect(self._on_matrix_queue)
        stop = QPushButton("Stop between cells")
        stop.setObjectName("generate_matrix_stop")
        stop.clicked.connect(self._sweep_stop.set)
        promote = QPushButton("Promote cell to run")
        promote.setObjectName("generate_matrix_promote")
        promote.clicked.connect(self._on_promote)
        buttons.addWidget(queue)
        buttons.addWidget(stop)
        buttons.addWidget(promote)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addStretch()
        self.guided._mode_combo.currentIndexChanged.connect(lambda _i: self._sync_matrix_axes())
        self.graph.editor.textChanged.connect(self._on_graph_text_for_matrix)
        self.graph.overrides.textChanged.connect(self._on_graph_text_for_matrix)
        self._sync_matrix_axes()
        return page

    def _on_graph_text_for_matrix(self) -> None:
        if self._use_graph.isChecked():
            self._sync_matrix_axes()

    def _graph_workflow(self) -> tuple[dict | None, str]:
        try:
            value, _overrides = parse_graph_submission(
                self.graph.editor.toPlainText(), self.graph.overrides.text(),
            )
        except ValueError as exc:
            return None, str(exc)
        return value, ""

    def _matrix_source_workflow(self) -> tuple[dict | None, str]:
        if self._use_graph.isChecked():
            return self._graph_workflow()
        fields = self._guided_fields()
        try:
            workflow, _overrides = plan_guided_workflow(
                fields["mode"],
                base_checkpoint=fields["base_checkpoint"],
                extra_checkpoint=fields["extra_checkpoint"],
                positive_prompt=fields["positive_prompt"],
                negative_prompt=fields["negative_prompt"],
                image_filename="placeholder.png",
                seed=fields["seed"],
                width=fields["width"],
                height=fields["height"],
            )
        except (UnknownWorkflowNodeError, AxisNotInWorkflow, ValueError) as exc:
            return None, str(exc)
        return workflow, ""

    def _sync_matrix_axes(self) -> None:
        workflow, error = self._matrix_source_workflow()
        first = -1
        model = self._axis.model()
        for index in range(self._axis.count()):
            key = self._axis.itemData(index)
            enabled = workflow is not None and find_node_id(workflow, AXES[key].class_types) is not None
            item = model.item(index)
            if item is not None:
                item.setEnabled(enabled)
            if enabled and first < 0:
                first = index
        current = model.item(self._axis.currentIndex())
        if current is not None and not current.isEnabled() and first >= 0:
            self._axis.setCurrentIndex(first)
        if error:
            self._matrix_message.setText(error)
            return
        self._refresh_estimate()

    def _load_existing_runs(self) -> None:
        snapshot = getattr(self._manager, "runs", None)
        if not callable(snapshot):
            return
        try:
            existing = snapshot()
        except Exception:
            return
        if isinstance(existing, (list, tuple)):
            for record in existing:
                self._filmstrip.upsert(record)

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Show another pane. Does not write the graph draft or the guided form."""
        if mode not in _MODES:
            return
        self._mode = mode
        self._stack.setCurrentIndex(_MODES.index(mode))
        for key, button in self._mode_buttons.items():
            button.setChecked(key == mode)

    def _refresh_estimate(self) -> None:
        _values, message = prepare_sweep(self._axis.currentData(), self._values.text())
        self._matrix_message.setText(message)

    def _guided_fields(self) -> dict:
        tab = self.guided
        workflow_mode = tab._mode_combo.currentData()
        return {
            "mode": workflow_mode,
            "workflow_mode": workflow_mode,
            "base_checkpoint": tab._base_ckpt_edit.text().strip(),
            "extra_checkpoint": tab._extra_ckpt_edit.text().strip(),
            "positive_prompt": tab._prompt_edit.text(),
            "negative_prompt": tab._negative_prompt_edit.text(),
            "seed": tab._seed_spin.value(),
            "width": tab._width_spin.value(),
            "height": tab._height_spin.value(),
        }

    def _on_open_browser(self) -> None:
        if not self._controller.open_external():
            self.graph.error.setText("Could not open the system browser.")
            return
        gpu_lease.note_external_browser(True)
        self.graph.error.setText(gpu_lease.scope_text())

    def _on_load_graph(self) -> None:
        record = self._filmstrip.selected_record()
        if record is None:
            self.graph.error.setText("Select a run in the filmstrip first.")
            return
        self.graph.load_record(record)

    def _on_upscale_selected(self) -> None:
        """Snapshot the filmstrip selection locally and upscale it (#749)."""
        record = self._filmstrip.selected_record()
        if record is None:
            self._upscale_message.setText("Select a run in the filmstrip first.")
            return
        local = getattr(record, "local_output_path", None)
        if isinstance(local, str) and local and os.path.isfile(local):
            self._upscale_source_id = record.prompt_id
            self._start_upscale_files([local])
            return
        if self._view_fetch is None:
            self._upscale_message.setText("Output fetch is unavailable for this run.")
            return
        filename, subfolder, kind = _first_output(record)
        if not filename:
            self._upscale_message.setText("Selected run has no downloadable output.")
            return
        self._upscale_source_id = record.prompt_id
        self._upscale_btn.setEnabled(False)
        self._upscale_message.setText("Downloading original and upscaling…")
        self._upscaler.start_remote(
            self._manager.fetch_output, filename, subfolder, kind,
            os.path.join(LOCAL_SOURCE_PATH, "Generated"),
        )

    def _start_upscale_files(self, paths: list) -> None:
        self._upscale_message.setText(f"Upscaling {len(paths)} file(s)…")
        self._upscale_btn.setEnabled(False)
        self._upscaler.start(paths)

    def _on_upscale_finished(self, outputs) -> None:
        self._upscale_btn.setEnabled(True)
        source = self._upscale_source_id
        self._upscale_source_id = None
        if not outputs:
            self._upscale_message.setText("Upscale finished with no output.")
            return
        for path in outputs:
            prompt_id = (
                f"{source}_upscaled"
                if isinstance(source, str) and source
                else os.path.basename(path)
            )
            self._filmstrip.upsert(SimpleNamespace(
                prompt_id=prompt_id,
                status="upscaled",
                surface_mode="upscale",
                outputs=(),
                workflow=None,
                local_output_path=path,
            ))
            self._filmstrip.select(prompt_id)
        self._upscale_message.setText(f"Upscaled → {os.path.basename(outputs[-1])}")

    def _on_upscale_error(self, message: str) -> None:
        self._upscale_btn.setEnabled(True)
        self._upscale_message.setText(message)

    def _on_queue_graph(self) -> None:
        try:
            workflow, overrides = parse_graph_submission(
                self.graph.editor.toPlainText(), self.graph.overrides.text(),
            )
        except (UnknownWorkflowNodeError, ValueError) as exc:
            self.graph.error.setText(str(exc))
            return
        self.graph.error.setText("")
        if self._controller.server_state != ServerState.READY:
            self.graph.error.setText("ComfyUI server is not running.")
            return
        meta = {"surface_mode": "graph", "applied_overrides": overrides or None}
        if not self._controller.run_http_action(lambda: self._queue_graph(workflow, meta)):
            self.graph.error.setText("Server is busy or not ready.")

    def _queue_graph(self, workflow: dict, meta: dict) -> None:
        refusal = try_admit("graph")
        if refusal:
            self._controller._publish_log(f"[workflow] {refusal}\n")
            return
        try:
            issue = _template_issue(self._manager, workflow)
            if issue:
                raise ValueError(issue)
            prompt_id = self._manager.queue_workflow(workflow, run_meta=meta)
            self._controller._publish_log(f"[workflow] Queued graph — prompt_id={prompt_id}\n")
            self._manager.wait_for_run(prompt_id, cancel=self._controller._cancel)
        except Exception as exc:
            self._controller._publish_log(f"[workflow] Error: {exc}\n")
        finally:
            gpu_lease.release("graph")

    def _on_matrix_queue(self) -> None:
        values, message = prepare_sweep(self._axis.currentData(), self._values.text())
        self._matrix_message.setText(message)
        if values is None:
            return
        if self._controller.server_state != ServerState.READY:
            self._matrix_message.setText("ComfyUI server is not running.")
            return
        fields = self._guided_fields()
        source, error = self._matrix_source_workflow()
        if error or source is None:
            self._matrix_message.setText(error or "This workflow cannot be swept.")
            return
        axis = self._axis.currentData()
        if find_node_id(source, AXES[axis].class_types) is None:
            self._matrix_message.setText(str(AxisNotInWorkflow(axis, AXES[axis].class_types)))
            return
        image = self.guided._image_edit.text().strip()
        needs_image = not self._use_graph.isChecked() and bool(WORKFLOW_MODES[fields["mode"]].get("image_node"))
        if needs_image and not image:
            self._matrix_message.setText("No control/reference image selected.")
            return
        preview = source
        issue = _template_issue(self._manager, preview)
        if issue:
            self._matrix_message.setText(issue)
            return
        job = MatrixJob(
            mode=fields["mode"],
            image_path=image,
            base_checkpoint=fields["base_checkpoint"],
            extra_checkpoint=fields["extra_checkpoint"],
            positive_prompt=fields["positive_prompt"],
            negative_prompt=fields["negative_prompt"],
            seed=fields["seed"],
            width=fields["width"],
            height=fields["height"],
            axis=self._axis.currentData(),
            values=tuple(values),
            workflow=source if self._use_graph.isChecked() else None,
            template_name="graph" if self._use_graph.isChecked() else None,
            applied_overrides=(json.loads(self.graph.overrides.text().strip() or "{}")
                               if self._use_graph.isChecked() else None),
        )
        self._sweep_stop.clear()
        if not self._controller.run_http_action(lambda: self._finish_matrix(job)):
            self._matrix_message.setText("Server is busy or not ready.")

    def _finish_matrix(self, job: MatrixJob) -> None:
        from shiboken6 import isValid

        result = self._run_matrix_job(job)
        if isValid(self) and not self._controller._closed:
            self._matrix_status.emit(result)

    def _run_matrix_job(self, job: MatrixJob, pressure_check=None, thermal_check=None) -> str:
        log = self._controller._publish_log
        try:
            if job.workflow is not None:
                workflow = job.workflow
                overrides = job.applied_overrides or {}
                template = job.template_name or "graph"
            else:
                cfg = WORKFLOW_MODES[job.mode]
                uploaded = "placeholder.png"
                if cfg.get("image_node"):
                    log(f"[workflow] Uploading {job.image_path}…\n")
                    uploaded = self._manager.upload_image(job.image_path)
                workflow, overrides = plan_guided_workflow(
                    job.mode,
                    base_checkpoint=job.base_checkpoint,
                    extra_checkpoint=job.extra_checkpoint,
                    positive_prompt=job.positive_prompt,
                    negative_prompt=job.negative_prompt,
                    image_filename=uploaded,
                    seed=job.seed,
                    width=job.width,
                    height=job.height,
                )
                template = cfg["template"]
            issue = _template_issue(self._manager, workflow)
            if issue:
                log(f"[workflow] Blocked by pre-flight validation: {issue}\n")
                return issue
            result = run_matrix_sweep(
                workflow=workflow,
                axis=job.axis,
                values=list(job.values),
                queue=lambda cell, meta: self._manager.queue_workflow(cell, run_meta=meta),
                wait_for_completion=lambda pid: self._manager.wait_for_run(
                    pid, cancel=self._controller._cancel,
                ),
                template_name=template,
                base_overrides=overrides,
                stop_check=lambda: self._sweep_stop.is_set() or self._controller._cancel.is_set(),
                pressure_check=pressure_check,
                thermal_check=thermal_check,
            )
        except Exception as exc:
            log(f"[workflow] Error: {exc}\n")
            return str(exc)
        log(f"[workflow] {_sweep_status(result)}\n")
        return _sweep_status(result)

    def _on_promote(self) -> None:
        record = self._filmstrip.selected_record()
        workflow = getattr(record, "workflow", None) if record is not None else None
        if not isinstance(workflow, dict):
            self._matrix_message.setText("Select a matrix cell to promote.")
            return
        if self._controller.server_state != ServerState.READY:
            self._matrix_message.setText("ComfyUI server is not running.")
            return
        width = self.guided._width_spin.value()
        height = self.guided._height_spin.value()
        parent = record.prompt_id
        template = getattr(record, "template_name", None)
        if not self._controller.run_http_action(
            lambda: self._queue_promoted(workflow, width, height, parent, template)
        ):
            self._matrix_message.setText("Server is busy or not ready.")

    def _queue_promoted(self, workflow, width: int, height: int, parent, template) -> None:
        refusal = try_admit("promoted")
        if refusal:
            self._controller._publish_log(f"[workflow] {refusal}\n")
            return
        try:
            queued, meta = build_promoted_submission(
                workflow,
                full_width=width,
                full_height=height,
                parent_prompt_id=parent,
                template_name=template,
            )
            prompt_id = self._manager.queue_workflow(queued, run_meta=meta)
            self._controller._publish_log(f"[workflow] Promoted cell — prompt_id={prompt_id}\n")
            self._manager.wait_for_run(prompt_id, cancel=self._controller._cancel)
        except Exception as exc:
            self._controller._publish_log(f"[workflow] Error: {exc}\n")
        finally:
            gpu_lease.release("promoted")

    def collect(self) -> dict:
        fields = self._guided_fields()
        fields.update({
            "surface_mode": self._mode,
            "image": self.guided._image_edit.text(),
            "graph_text": self.graph.editor.toPlainText(),
            "graph_dirty": self.graph.dirty,
        })
        return fields

    def set_config(self, config: dict) -> None:
        if not isinstance(config, dict):
            return
        tab = self.guided
        _set_text(tab._base_ckpt_edit, config.get("base_checkpoint"))
        _set_text(tab._extra_ckpt_edit, config.get("extra_checkpoint"))
        _set_text(tab._image_edit, config.get("image"))
        if isinstance(config.get("positive_prompt"), str):
            tab._prompt_edit.setText(config["positive_prompt"])
        if isinstance(config.get("negative_prompt"), str):
            tab._negative_prompt_edit.setText(config["negative_prompt"])
        _set_spin(tab._seed_spin, config.get("seed"))
        _set_spin(tab._width_spin, config.get("width"))
        _set_spin(tab._height_spin, config.get("height"))
        mode = config.get("workflow_mode")
        if isinstance(mode, str):
            index = tab._mode_combo.findData(mode)
            if index >= 0:
                tab._mode_combo.setCurrentIndex(index)
        graph_text = config.get("graph_text")
        if isinstance(graph_text, str):
            self.graph.replace_text(graph_text)
        surface_mode = config.get("surface_mode")
        if isinstance(surface_mode, str):
            self.set_mode(surface_mode)

    def apply_pinned_run(self, run) -> None:
        config = getattr(run, "config", None)
        if isinstance(config, dict):
            self.set_config(config)


def _set_text(widget, value) -> None:
    if isinstance(value, str):
        widget.setText(value)


def _set_spin(widget, value) -> None:
    if isinstance(value, int) and not isinstance(value, bool):
        widget.setValue(value)


def _attach_graph_actions(surface: GenerateSurface) -> None:
    row = QHBoxLayout()
    open_browser = QPushButton("Open in External Browser")
    open_browser.setObjectName("generate_graph_open")
    open_browser.clicked.connect(surface._on_open_browser)
    load = QPushButton("Load selected run")
    load.setObjectName("generate_graph_load")
    load.clicked.connect(surface._on_load_graph)
    queue = QPushButton("Queue graph")
    queue.setObjectName("generate_graph_queue")
    queue.clicked.connect(surface._on_queue_graph)
    row.addWidget(open_browser)
    row.addWidget(load)
    row.addWidget(queue)
    row.addStretch()
    surface.graph.layout().addLayout(row)
