"""Diff & Apply widget for validated guidance suggestions (#752).

Renders each suggestion in a ``GuidanceValidation`` as a diff row
(node / field / old → new / reason) with a per-row Apply toggle — never a
paragraph of prose. One Re-queue button patches the selected rows through
``apply_validated()`` (the only sanctioned patch path; raw
``apply_overrides()`` is never the boundary), writes the patched graph to a
new workflow file, and queues it as a labeled assistant-suggested variant.

No silent auto-apply, ever: every applied change is an explicit user action
on an explicit diff row, and stale or hallucination-flagged batches refuse
outright — the widget will not offer them.
"""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from copy import deepcopy

from backend.src.comfy_matrix import gpu_lease, try_admit
from backend.src.constants import LOCAL_SOURCE_PATH
from backend.src.core.gpu_vram_estimate import estimate_job_gb
from backend.src.core.guidance_schema import (
    GuidanceValidation,
    ModelSwap,
    Verdict,
    apply_validated,
)
from backend.src.core.guidance_trajectory import (
    GuidanceTrajectory,
    append_step,
    bind_variant,
    build_requeue_trajectory,
    load_existing_trajectory,
    save_trajectory,
    trajectory_sidecar_path,
)
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.guidance.guidance_evidence_widgets import AbstentionPanel, EvidenceRowExtras

GUIDANCE_OWNER = "guidance"
VARIANT_LABEL = "assistant-suggested"


def variant_workflow_dir() -> str:
    return os.path.join(LOCAL_SOURCE_PATH, "Generated", "variants")


def write_variant_file(patched: dict, *, source_id: str | None, directory: str | None = None) -> str:
    """Write *patched* to a new workflow file; never touches the source run."""
    target_dir = directory or variant_workflow_dir()
    os.makedirs(target_dir, exist_ok=True)
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", source_id or "workflow")[:100]
    path = os.path.join(target_dir, f"{stem}_variant_{uuid.uuid4().hex}.json")
    with open(path, "x", encoding="utf-8") as handle:
        json.dump(patched, handle, indent=2)
    return path


def filtered_validation(
    validation: GuidanceValidation, selected: list
) -> GuidanceValidation:
    """A validation carrying only *selected* verdicts.

    Stale/hallucination flags travel with it, so ``apply_validated()``
    still refuses whole untrusted batches even for a per-row selection.
    """
    return GuidanceValidation(
        response=validation.response,
        verdicts=tuple(selected),
        stale=validation.stale,
        hallucination_flagged=validation.hallucination_flagged,
        notes=validation.notes,
    )


def build_patch(workflow: dict, validation: GuidanceValidation, selected: list) -> dict | None:
    """Patch *workflow* with exactly *selected* verdicts; None when unsafe."""
    if not selected:
        return None
    return apply_validated(workflow, filtered_validation(validation, list(selected)))


def _short(value, limit: int = 60) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[: limit - 1] + "…"


class _SubmissionBus(QObject):
    queued = Signal(str)
    trajectory = Signal(object)
    error = Signal(str)


class GuidanceDiffWidget(QWidget):
    """Per-row diff list + re-queue for one validated guidance response."""

    variant_queued = Signal(str)
    trajectory_updated = Signal(object)
    guidance_error = Signal(str)
    paths_requested = Signal(tuple)
    node_highlight_requested = Signal(str)

    def __init__(self, controller=None, manager=None, variant_dir: str | None = None, parent=None) -> None:
        super().__init__(parent)
        self._controller = controller
        self._manager = manager
        self._variant_dir = variant_dir
        self._workflow: dict | None = None
        self._validation: GuidanceValidation | None = None
        self._source_id: str | None = None
        self._source_mode: str | None = None
        self._busy = False
        self._feedback = ""
        self._toggles: list[QCheckBox] = []
        self._toggle_verdicts: list = []
        self._summaries: list[str] = []
        self._submit_thread: threading.Thread | None = None
        self._bus = _SubmissionBus()
        self._bus.queued.connect(self.variant_queued)
        self._bus.trajectory.connect(self.trajectory_updated)
        self._bus.error.connect(self.guidance_error)
        self._build_ui()
        self.variant_queued.connect(self._on_variant_queued)
        self.guidance_error.connect(self._on_guidance_error)

    def set_feedback(self, text: str) -> None:
        """Original user complaint carried into the next trajectory step (#754)."""
        self._feedback = text.strip() if isinstance(text, str) else ""

    # ── UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._banner = QLabel("")
        self._banner.setWordWrap(True)
        self._banner.setObjectName("guidance_banner")
        self._banner.setVisible(False)
        root.addWidget(self._banner)
        scroll = QScrollArea()
        scroll.setObjectName("guidance_rows_scroll")
        scroll.setWidgetResizable(True)
        self._rows_host = QWidget()
        self._rows_host.setObjectName("guidance_rows")
        self._rows = QVBoxLayout(self._rows_host)
        self._rows.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._rows_host)
        scroll.setMinimumHeight(120)
        root.addWidget(scroll, stretch=1)
        self._dataset_note = QLabel("")
        self._dataset_note.setWordWrap(True)
        self._dataset_note.setVisible(False)
        root.addWidget(self._dataset_note)
        action_row = QHBoxLayout()
        self._requeue_btn = QPushButton("Re-queue as variant")
        self._requeue_btn.setObjectName("guidance_requeue_btn")
        self._requeue_btn.setToolTip("Queue the checked changes as a labeled assistant-suggested variant (#752)")
        self._requeue_btn.clicked.connect(self._on_requeue)
        self._requeue_btn.setEnabled(False)
        self._status = QLabel("No validated suggestions yet.")
        self._status.setWordWrap(True)
        self._status.setObjectName("guidance_status")
        action_row.addWidget(self._requeue_btn)
        action_row.addWidget(self._status, stretch=1)
        root.addLayout(action_row)

    # ── Model ─────────────────────────────────────────────────────────

    def set_guidance(
        self,
        *,
        workflow: dict,
        validation: GuidanceValidation,
        source_prompt_id: str | None = None,
        source_mode: str | None = None,
    ) -> None:
        """Render *validation* against *workflow*; arms re-queue when safe."""
        if self._busy:
            self.note("Wait for the current variant before changing the guidance source.")
            return
        self._workflow = deepcopy(workflow)
        self._validation = validation
        self._source_id = source_prompt_id
        self._source_mode = source_mode
        self._render()

    def set_source(self, source_prompt_id: str, workflow: dict, source_mode: str | None = None) -> None:
        """Remember the critiqued run while validated suggestions are pending."""
        if self._busy:
            self.note("Wait for the current variant before changing the guidance source.")
            return
        self._workflow = deepcopy(workflow)
        self._validation = None
        self._source_id = source_prompt_id
        self._source_mode = source_mode
        self._render()

    def clear_guidance(self) -> None:
        if self._busy:
            return
        self._workflow = None
        self._validation = None
        self._source_id = None
        self._source_mode = None
        self._render()

    def note(self, message: str) -> None:
        self._status.setText(message)

    def valid_toggles(self) -> list[QCheckBox]:
        return list(self._toggles)

    def summaries(self) -> list[str]:
        return list(self._summaries)

    def selected_verdicts(self) -> list:
        return [
            v
            for v, box in zip(self._toggle_verdicts, self._toggles, strict=True)
            if box.isChecked()
        ]

    # ── Rendering ─────────────────────────────────────────────────────

    def _clear_rows(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._toggles = []
        self._toggle_verdicts = []
        self._summaries = []

    def _render(self) -> None:
        self._clear_rows()
        validation = self._validation
        if validation is None:
            self._banner.setVisible(False)
            self._dataset_note.setVisible(False)
            if self._workflow is not None:
                self._status.setText(
                    f"Source run {self._source_id or ''} loaded — validated suggestions will appear here."
                )
            else:
                self._status.setText("No validated suggestions yet.")
            self._requeue_btn.setEnabled(False)
            return
        if validation.notes:
            self._banner.setText("\n".join(validation.notes))
            self._banner.setVisible(True)
        else:
            self._banner.setVisible(False)
        for verdict in validation.verdicts:
            self._add_row(verdict)
            extras = EvidenceRowExtras(verdict.change, validation)
            extras.paths_requested.connect(self.paths_requested)
            self._rows.addWidget(extras)
        if validation.response.needs:
            panel = AbstentionPanel(
                validation.response.needs, validation.response.diagnosis or "",
                tuple(ref for v in validation.verdicts for ref in v.change.evidence),
            )
            panel.pick_list_requested.connect(self.paths_requested)
            self._rows.addWidget(panel)
        if not validation.verdicts:
            self._rows.addWidget(QLabel("No suggestions in this response."))
        dataset = validation.response.dataset_guidance
        if isinstance(dataset, str) and dataset.strip():
            self._dataset_note.setText(f"Dataset guidance (apply in Train): {dataset.strip()}")
            self._dataset_note.setVisible(True)
        else:
            self._dataset_note.setVisible(False)
        self._refresh_requeue_state()

    def _add_row(self, verdict) -> None:
        change = verdict.change
        summary = (
            f"{change.node_id}.{change.input_name}: "
            f"{_short(change.from_value)} → {_short(change.to_value)}"
        )
        self._summaries.append(summary)
        if verdict.status == Verdict.VALID:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            box = QCheckBox(summary)
            box.setChecked(True)
            box.setObjectName(f"guidance_apply_{change.node_id}_{change.input_name}")
            box.setToolTip(change.reason or "")
            box.toggled.connect(lambda _checked: self._refresh_requeue_state())
            self._toggles.append(box)
            self._toggle_verdicts.append(verdict)
            focus_btn = QPushButton("Focus")
            focus_btn.setObjectName(f"guidance_focus_{change.node_id}_{change.input_name}")
            focus_btn.setToolTip(f"Highlight node {change.node_id} in embedded ComfyUI graph (#755)")
            focus_btn.setFixedWidth(54)
            focus_btn.clicked.connect(lambda _=False, nid=change.node_id: self.node_highlight_requested.emit(str(nid)))
            row_layout.addWidget(box, stretch=1)
            row_layout.addWidget(focus_btn)
            self._rows.addWidget(row_widget)
            if change.reason:
                reason = QLabel(change.reason)
                reason.setWordWrap(True)
                reason.setProperty("class", "guidance-reason")
                self._rows.addWidget(reason)
            return
        if verdict.status == Verdict.MISSING_ASSET and isinstance(change, ModelSwap):
            label = QLabel(f"{summary}\nNeeds install: {_short(change.to_value)} — not applied.")
        else:
            label = QLabel(f"{summary}\nNot applied ({verdict.status}): {verdict.detail}")
        label.setWordWrap(True)
        label.setProperty("class", "guidance-rejected")
        label.setObjectName(f"guidance_row_{change.node_id}_{change.input_name}")
        self._rows.addWidget(label)

    def _refresh_requeue_state(self) -> None:
        for label in self.findChildren(QLabel):
            label.setTextFormat(Qt.TextFormat.PlainText)
        validation = self._validation
        if (
            self._busy
            or validation is None
            or validation.stale
            or validation.hallucination_flagged
        ):
            self._requeue_btn.setEnabled(False)
            return
        self._requeue_btn.setEnabled(any(box.isChecked() for box in self._toggles))

    # ── Re-queue ──────────────────────────────────────────────────────

    def _on_requeue(self) -> None:
        if self._busy:
            return
        if self._controller is None or self._manager is None:
            self._status.setText("Queueing is unavailable here.")
            return
        from backend.src.constants.comfy import ServerState

        if self._controller.server_state != ServerState.READY:
            self._status.setText("ComfyUI server is not running.")
            return
        validation = self._validation
        if validation is None or self._workflow is None:
            self._status.setText("No validated suggestions to re-queue.")
            return
        selected = self.selected_verdicts()
        patched = build_patch(self._workflow, validation, selected)
        if patched is None:
            self._status.setText("Nothing safe to apply — refusing to queue.")
            return
        meta: dict = {"parent_prompt_id": self._source_id, "variant_label": VARIANT_LABEL}
        if self._source_mode:
            meta["surface_mode"] = self._source_mode
        traj = build_requeue_trajectory(
            existing=None,
            parent_prompt_id=self._source_id,
            selected=selected,
            feedback=self._feedback,
        )
        meta["guidance_trajectory"] = traj.to_dict()
        self._busy = True
        self._status.setText("Queueing variant…")
        self._requeue_btn.setEnabled(False)
        if not self._controller.run_http_action(lambda: self._submit_variant(patched, meta)):
            self._busy = False
            self._status.setText("Server is busy or not ready.")
            self._refresh_requeue_state()

    def _submit_variant(self, patched: dict, meta: dict) -> None:
        refusal = try_admit(
            GUIDANCE_OWNER,
            estimated_gb=estimate_job_gb(GUIDANCE_OWNER, workflow=patched),
        )
        if refusal:
            self._bus.error.emit(refusal)
            return
        try:
            existing = load_existing_trajectory(self._manager, meta["parent_prompt_id"])
            pending = GuidanceTrajectory.from_dict(meta["guidance_trajectory"])
            if pending.latest is None:
                raise ValueError("No guidance step to queue.")
            traj = append_step(existing, pending.latest)
            meta["guidance_trajectory"] = traj.to_dict()
            write_variant_file(patched, source_id=meta["parent_prompt_id"], directory=self._variant_dir)
            prompt_id = self._manager.queue_workflow(patched, run_meta=meta)
            cancel = getattr(self._controller, "_cancel", None)
            completed = self._manager.wait_for_run(prompt_id, cancel=cancel)
            traj = bind_variant(traj, prompt_id)
            updater = getattr(self._manager, "update_run_meta", None)
            if callable(updater):
                updater(prompt_id, {"guidance_trajectory": traj.to_dict()})
            self._persist_sidecar(traj)
            if not completed:
                self._bus.error.emit(f"Variant {prompt_id} did not complete; inspect the run status.")
                return
        except Exception as exc:
            self._bus.error.emit(str(exc))
            return
        finally:
            gpu_lease.release(GUIDANCE_OWNER)
        self._bus.queued.emit(prompt_id)
        self._bus.trajectory.emit(traj)

    def _on_variant_queued(self, prompt_id: str) -> None:
        self._status.setText(f"Queued assistant-suggested variant — prompt_id={prompt_id}")
        self._busy = False
        self._refresh_requeue_state()

    def _persist_sidecar(self, traj) -> None:
        directory = self._variant_dir or variant_workflow_dir()
        try:
            variant_id = traj.latest.variant_prompt_id if traj.latest else None
            save_trajectory(trajectory_sidecar_path(directory, variant_id or traj.root_prompt_id), traj)
        except OSError:
            return

    def _on_guidance_error(self, message: str) -> None:
        self._busy = False
        self._status.setText(message)
        self._refresh_requeue_state()
