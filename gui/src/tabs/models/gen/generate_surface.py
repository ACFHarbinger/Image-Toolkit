"""Unified Generate surface: Guided | Graph, shared filmstrip, matrix sweeps.

External-only (#729): Graph does not create a WebEngine view. The canvas
is the system browser. A local JSON draft is kept across mode switches
and is never replaced while it has unsaved edits (#739). Matrix mode
queues one existing ``queue_workflow`` per cell on one GPU lease (#740).
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass

from backend.src.comfy_matrix import (
    AxisNotInWorkflow,
    UnknownWorkflowNodeError,
    build_promoted_submission,
    gpu_lease,
    output_paths,
    parse_graph_submission,
    prepare_sweep,
    run_matrix_sweep,
)
from backend.src.constants.comfy import ServerState
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.tabs.models.gen.comfy_generate_tab import (
    WORKFLOW_MODES,
    ComfyUITab,
    plan_guided_workflow,
)

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
        return f"GPU lease is held by {holder}."
    if result.stopped == "cap":
        return "Sweep exceeds the cell cap."
    if result.stopped == "pressure":
        return f"Stopped between cells under VRAM pressure after {count} cell(s)."
    if result.stopped == "stop":
        return f"Stopped between cells after {count} cell(s)."
    return f"Queued {count} cells. Parent {result.parent_prompt_id}."


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)


class OutputFilmstrip(QWidget):
    """One strip for guided and graph runs. Matrix cells share a grid."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("generate_filmstrip")
        self._records: dict[str, object] = {}
        self._order: list[str] = []
        self._selected_id: str | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._strip = QHBoxLayout()
        self._grids = QVBoxLayout()
        root.addLayout(self._strip)
        root.addLayout(self._grids)

    def upsert(self, record) -> None:
        prompt_id = getattr(record, "prompt_id", None)
        if not isinstance(prompt_id, str):
            return
        if prompt_id not in self._records:
            self._order.append(prompt_id)
        self._records[prompt_id] = record
        self._rebuild()

    def selected_record(self):
        if self._selected_id is None:
            return None
        return self._records.get(self._selected_id)

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

    def _cell(self, record) -> QPushButton:
        prompt_id = record.prompt_id
        button = QPushButton(_cell_text(record))
        button.setCheckable(True)
        button.setChecked(prompt_id == self._selected_id)
        button.setObjectName(f"filmstrip_{prompt_id}")
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


def _cell_text(record) -> str:
    paths = output_paths(record)
    path = paths[0] if paths else "no output"
    status = getattr(record, "status", "")
    mode = getattr(record, "surface_mode", None) or ""
    axis = getattr(record, "sweep_axis", None)
    extra = f" {axis}={record.sweep_value}" if axis else ""
    return f"{record.prompt_id} {status}{extra} {path} {mode}".strip()


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
        self.guided = ComfyUITab(enable_manager=enable_manager, controller=self._controller)
        self.graph = GraphDraft()
        self._filmstrip = OutputFilmstrip()
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
            "One axis, 3–9 values, one GPU lease. Cells queue through the existing "
            "workflow API at preview size. Promote clones the selected cell at the guided size."
        ))
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
        self._refresh_estimate()
        return page

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

    def _on_load_graph(self) -> None:
        record = self._filmstrip.selected_record()
        if record is None:
            self.graph.error.setText("Select a run in the filmstrip first.")
            return
        self.graph.load_record(record)

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
        if not gpu_lease.try_acquire("graph"):
            self._controller._publish_log(f"[workflow] GPU lease is held by {gpu_lease.owner}.\n")
            return
        try:
            prompt_id = self._manager.queue_workflow(workflow, run_meta=meta)
            self._controller._publish_log(f"[workflow] Queued graph — prompt_id={prompt_id}\n")
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
        image = self.guided._image_edit.text().strip()
        if not image:
            self._matrix_message.setText("No control/reference image selected.")
            return
        fields = self._guided_fields()
        try:
            preview, _overrides = plan_guided_workflow(
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
            self._matrix_message.setText(str(exc))
            return
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
        )
        self._sweep_stop.clear()
        if not self._controller.run_http_action(lambda: self._finish_matrix(job)):
            self._matrix_message.setText("Server is busy or not ready.")

    def _finish_matrix(self, job: MatrixJob) -> None:
        self._matrix_status.emit(self._run_matrix_job(job))

    def _run_matrix_job(self, job: MatrixJob, pressure_check=None) -> str:
        log = self._controller._publish_log
        try:
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
            issue = _template_issue(self._manager, workflow)
            if issue:
                log(f"[workflow] Blocked by pre-flight validation: {issue}\n")
                return issue
            template = WORKFLOW_MODES[job.mode]["template"]
            result = run_matrix_sweep(
                workflow=workflow,
                axis=job.axis,
                values=list(job.values),
                queue=lambda cell, meta: self._manager.queue_workflow(cell, run_meta=meta),
                template_name=template,
                base_overrides=overrides,
                stop_check=self._sweep_stop.is_set,
                pressure_check=pressure_check,
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
        if not gpu_lease.try_acquire("promoted"):
            self._controller._publish_log(f"[workflow] GPU lease is held by {gpu_lease.owner}.\n")
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
