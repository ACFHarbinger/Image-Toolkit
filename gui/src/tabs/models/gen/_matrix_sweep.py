"""Matrix sweep mode of the Generate surface (#740), split from generate_surface."""

from __future__ import annotations

import json
from dataclasses import dataclass

from middleware.src.comfy_matrix import (
    AXES,
    AxisNotInWorkflow,
    UnknownWorkflowNodeError,
    find_node_id,
    gpu_lease,
    prepare_sweep,
    run_matrix_sweep,
)
from middleware.src.constants.comfy import ServerState
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.src.tabs.models.gen.comfy_generate_tab import (
    WORKFLOW_MODES,
    plan_guided_workflow,
)


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
        return gpu_lease.refusal_text()
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


class MatrixSweepMixin:
    """GenerateSurface methods for the matrix page and its sweep jobs."""

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
