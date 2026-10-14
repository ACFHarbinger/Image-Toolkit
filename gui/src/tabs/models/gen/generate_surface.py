"""Unified Generate surface: Guided | Graph, shared filmstrip, matrix sweeps.

External-only (#729): Graph does not create a WebEngine view. The canvas
is the system browser. A local JSON draft is kept across mode switches
and is never replaced while it has unsaved edits (#739). Matrix mode
queues one existing ``queue_workflow`` per cell on one GPU lease (#740).
"""
from __future__ import annotations

import json
import os
import threading
from types import SimpleNamespace

from backend.src.comfy_matrix import (
    UnknownWorkflowNodeError,
    build_promoted_submission,
    gpu_lease,
    parse_graph_submission,
    prepare_sweep,
    try_admit,
)
from backend.src.constants import LOCAL_SOURCE_PATH
from backend.src.constants.comfy import ServerState
from backend.src.core.gpu_vram_estimate import estimate_job_gb
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
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
    ComfyUITab,
)
from gui.src.tabs.models.upscale_handoff import UpscaleRunner

from ._matrix_sweep import MatrixJob, MatrixSweepMixin, _sweep_status, _template_issue  # noqa: F401
from .output_filmstrip import (  # noqa: F401  re-exported for callers and tests
    OutputFilmstrip,
    _cell_text,
    _clear_layout,
    _decode_thumbnail,
    _first_output,
    _manager_view_fetcher,
    _scroll,
)

_MODES = ("guided", "graph", "matrix")


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


class GenerateSurface(MatrixSweepMixin, QWidget):
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
        self._upscale_btn = QPushButton("Upscale selected")
        self._upscale_btn.setObjectName("generate_upscale_selected")
        self._upscale_btn.setToolTip("Upscale the filmstrip selection with Real-ESRGAN anime_6B (#749)")
        self._upscale_btn.clicked.connect(self._on_upscale_selected)
        self._upscale_message = QLabel("")
        self._upscale_message.setWordWrap(True)
        self._upscale_message.setObjectName("generate_upscale_status")
        # Removed from the layout, but kept parented (and hidden) so they are
        # owned by the surface instead of floating as stray top-level windows.
        for widget in (self._filmstrip, self._upscale_btn, self._upscale_message):
            widget.setParent(self)
            widget.hide()
        self._stack = QStackedWidget()
        self._stack.addWidget(self.guided)
        self._stack.addWidget(self.graph)
        self._stack.addWidget(self._matrix_page())
        root.addWidget(self._stack, stretch=1)
        root.addLayout(self._mode_row())

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


    def _graph_workflow(self) -> tuple[dict | None, str]:
        try:
            value, _overrides = parse_graph_submission(
                self.graph.editor.toPlainText(), self.graph.overrides.text(),
            )
        except ValueError as exc:
            return None, str(exc)
        return value, ""


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

    def highlight_node(self, node_id: str | int) -> bool:
        """Delegate node highlighting to ComfyUITab (#755)."""
        self.set_mode("guided")
        if hasattr(self.guided, "highlight_node"):
            return self.guided.highlight_node(node_id)
        return False

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
        refusal = try_admit(
            "graph",
            estimated_gb=estimate_job_gb("graph", workflow=workflow),
        )
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
        refusal = try_admit(
            "promoted",
            estimated_gb=estimate_job_gb("promoted", width=width, height=height, workflow=workflow),
        )
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
