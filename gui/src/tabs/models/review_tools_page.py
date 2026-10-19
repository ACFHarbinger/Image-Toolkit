"""Review destination page of the Deep Learning workspace (split from dl_workspace_host)."""
from __future__ import annotations

import os
import threading
from copy import deepcopy
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.guidance.pair_loader import ComparisonPairLoader
from gui.src.components.guidance.what_changed_overlay import WhatChangedOverlay
from gui.src.modules.events import ImportPathsIntent
from gui.src.preferences import PreferenceStore, PrefKeys
from gui.src.tabs.models.dl_workspace_components import (
    ActionableEmptyState,
    GuidedOnboardingCard,
)
from gui.src.tabs.models.guidance_diff_widget import GuidanceDiffWidget
from gui.src.tabs.models.review_vision_tools import ReviewVisionPanel
from gui.src.tabs.models.upscale_handoff import UpscaleRunner

_DESTINATIONS = (
    ("train", "Train"),
    ("generate", "Generate"),
    ("review", "Review"),
    ("runs", "Runs"),
)


if TYPE_CHECKING:
    from .dl_workspace_host import DeepLearningWorkspaceHost


class _SuggestBus(QObject):
    finished = Signal(int, object, str)


class _ReviewToolsPage(QWidget):
    """Review destination with onboarding, empty state, and evaluation/inference tools (#731, #735)."""

    def __init__(
        self,
        host: DeepLearningWorkspaceHost,
        preference_store: PreferenceStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._host = host
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.onboarding = GuidedOnboardingCard(
            destination="review",
            preference_def=PrefKeys.DL_ONBOARDING_REVIEW_DISMISSED,
            preference_store=preference_store,
        )
        layout.addWidget(self.onboarding)

        self.empty_state = ActionableEmptyState(
            title="No Output Selected for Review",
            description="Select an output from your recent runs or generate a new image to inspect with R3GAN or MetaCLIP.",
            actions=[("Go to Generate", lambda: host.activate_route("generate"))],
        )
        self.empty_state.setObjectName("dl_review_empty_state")
        layout.addWidget(self.empty_state)

        row = QHBoxLayout()
        row.addWidget(QLabel("Review tool:"))
        self._eval_btn = QPushButton("R3GAN Evaluation")
        self._clip_btn = QPushButton("MetaCLIP Inference")
        row.addWidget(self._eval_btn)
        row.addWidget(self._clip_btn)
        row.addStretch()
        layout.addLayout(row)

        self._compare_host = QWidget()
        self._compare_host.setObjectName("dl_compare_canvas")
        self._compare_host.setMinimumHeight(280)
        self._compare_layout = QVBoxLayout(self._compare_host)
        self._compare_layout.setContentsMargins(0, 0, 0, 0)
        self._what_changed = WhatChangedOverlay(self._compare_host)
        self._what_changed.setObjectName("dl_what_changed")
        self._compare_layout.addWidget(self._what_changed)
        self._pair_loader = ComparisonPairLoader(self)
        self._pair_loader.loaded.connect(self._on_pair_loaded)
        self._pair_loader.failed.connect(self._on_pair_failed)
        self._pair_loader.persist_failed.connect(self._on_verdict_persist_failed)
        self._pair_loader.persisted.connect(self._on_verdict_persisted)
        self._verdict_pending = False
        self._pair_generation = 0
        self._bound_pair = None
        self._pair_cache_dir: str | None = None
        self._pair_fetch = None
        layout.addWidget(self._compare_host, stretch=1)

        upscale_row = QHBoxLayout()
        self._upscale_btn = QPushButton("Send to Upscale")
        self._upscale_btn.setObjectName("dl_review_upscale_btn")
        self._upscale_btn.setToolTip("Upscale the first compared image with Real-ESRGAN anime_6B (#749)")
        self._upscale_btn.clicked.connect(self._on_upscale)
        self._upscale_status = QLabel("")
        self._upscale_status.setWordWrap(True)
        self._upscale_status.setObjectName("dl_review_upscale_status")
        upscale_row.addWidget(self._upscale_btn)
        upscale_row.addWidget(self._upscale_status, stretch=1)
        layout.addLayout(upscale_row)
        self._upscaler = UpscaleRunner(self)
        self._upscaler.finished.connect(self._on_upscale_finished)
        self._upscaler.error.connect(self._on_upscale_error)

        self._vision = ReviewVisionPanel(vault=getattr(host, "_vault_manager", None))
        layout.addWidget(self._vision)
        load_row = QHBoxLayout()
        self._load_selection_btn = QPushButton("Load selected Generate run")
        self._load_selection_btn.setObjectName("dl_guidance_load_btn")
        self._load_selection_btn.setToolTip("Use the Generate filmstrip selection as the critiqued run (#752)")
        self._load_selection_btn.clicked.connect(self._on_load_generate_selection)
        self._suggest_btn = QPushButton("Suggest workflow changes")
        self._suggest_btn.setObjectName("dl_guidance_suggest_btn")
        self._suggest_btn.setToolTip("Request a schema suggestion, validate it, and show it here")
        self._suggest_btn.clicked.connect(self.suggest_from_workflow)
        load_row.addWidget(self._load_selection_btn)
        load_row.addWidget(self._suggest_btn)
        load_row.addStretch()
        self._suggest_approve = QCheckBox(
            "Also approve sending workflow values, local OCR text, and feedback/history for suggestions."
        )
        self._suggest_approval_key = None
        self._suggest_approve.toggled.connect(self._approve_suggestion_payload)
        layout.addWidget(self._suggest_approve)
        for field in (self._vision._endpoint, self._vision._model, self._vision._note):
            field.textChanged.connect(lambda *_: self._suggest_approve.setChecked(False))
        self._suggest_generation = 0
        self._suggest_context: dict[int, tuple] = {}
        self._suggest_thread: threading.Thread | None = None
        self._suggest_closed = threading.Event()
        closed = self._suggest_closed
        self.destroyed.connect(lambda *_: closed.set())
        # Unparented: a deleted page must not own the object the worker emits on.
        self._suggest_bus = _SuggestBus()
        self._suggest_bus.finished.connect(self._on_suggestion)
        layout.addLayout(load_row)
        from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController

        _controller = ComfyWorkspaceController.instance()
        self._guidance = GuidanceDiffWidget(controller=_controller, manager=_controller.manager)
        self._guidance.paths_requested.connect(self._send_guidance_paths)
        self._guidance.setObjectName("dl_guidance_diff")
        layout.addWidget(self._guidance)
        self._what_changed.feedback_changed.connect(self._guidance.set_feedback)
        self._what_changed.feedback_changed.connect(lambda *_: self._suggest_approve.setChecked(False))
        self._what_changed.verdict_chosen.connect(self._on_guidance_verdict)
        self._guidance.trajectory_updated.connect(self._on_trajectory_updated)
        self._guidance.node_highlight_requested.connect(self._host.highlight_node)

        self.set_compare_paths([])

        self._stack = QStackedWidget()
        from gui.src.tabs.models.meta_clip_inference_tab import MetaCLIPInferenceTab
        from gui.src.tabs.models.r3gan_evaluate_tab import R3GANEvaluateTab

        self._eval = R3GANEvaluateTab()
        self._clip = MetaCLIPInferenceTab()
        self._stack.addWidget(self._eval)
        self._stack.addWidget(self._clip)
        layout.addWidget(self._stack, stretch=1)
        self._eval_btn.clicked.connect(lambda: self._stack.setCurrentWidget(self._eval))
        self._clip_btn.clicked.connect(lambda: self._stack.setCurrentWidget(self._clip))

    def set_compare_paths(self, paths: list[str]) -> None:
        """Show *paths* in the shared pan/zoom/A-B/diff view."""
        self._invalidate_pair_load()
        self._what_changed.clear()
        self._replace_compare_view(paths)

    def _replace_compare_view(self, paths: list[str]) -> None:
        from gui.src.windows.image_compare_window import ImageCompareWindow

        self.empty_state.setVisible(not paths)
        self._invalidate_suggestion()
        self._vision.set_image(paths[0] if paths else None)
        if getattr(self, "_compare_paths", None) == paths:
            return
        self._compare_paths = list(paths)
        self._clear_compare_view()
        if not paths:
            empty = QLabel("Pin an image to compare it.")
            empty.setObjectName("dl_compare_empty")
            self._compare_layout.insertWidget(0, empty)
            return
        view = ImageCompareWindow(paths, parent=self._compare_host, embedded=True)
        view.setObjectName("dl_compare_view")
        self._compare_layout.insertWidget(0, view)

    def _clear_compare_view(self) -> None:
        """Replace the compare view/empty label without disposing the overlay."""
        for index in range(self._compare_layout.count() - 1, -1, -1):
            item = self._compare_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is None or widget is self._what_changed:
                continue
            self._compare_layout.takeAt(index)
            widget.setParent(None)
            widget.deleteLater()

    def _send_guidance_paths(self, paths) -> None:
        self._host._on_import_paths(ImportPathsIntent(module_id="dl.train", paths=tuple(paths), origin="guidance"))

    def _invalidate_pair_load(self) -> None:
        self._pair_generation += 1
        self._bound_pair = None
        self._what_changed.set_voting_enabled(False)

    def prepare_dispose(self) -> None:
        self._suggest_closed.set()
        self._invalidate_suggestion()
        self._invalidate_pair_load()

    def _on_trajectory_updated(self, traj) -> None:
        from middleware.src.core.guidance_pair import pair_ids_from_trajectory

        self._invalidate_suggestion()
        self._invalidate_pair_load()
        self._what_changed.set_trajectory(traj)
        refs = pair_ids_from_trajectory(traj, self._what_changed.variant_id())
        if refs is None:
            return
        generation = self._pair_generation
        self._pair_loader.start(
            self._guidance._manager,
            parent_prompt_id=refs.parent_prompt_id,
            variant_prompt_id=refs.variant_prompt_id,
            generation=generation,
            cache_dir=self._pair_cache_dir,
            fetch=self._pair_fetch,
        )

    def _on_pair_loaded(self, bound) -> None:
        from middleware.src.core.guidance_pair import pair_files_alive, pair_matches_trajectory

        if bound.generation != self._pair_generation:
            return
        traj = self._what_changed.trajectory()
        if not pair_matches_trajectory(bound, traj, self._what_changed.variant_id()):
            return
        if not pair_files_alive(bound):
            self._what_changed.set_voting_enabled(False)
            return
        self._bound_pair = bound
        self._replace_compare_view(bound.paths)
        record = self._guidance._manager.get_run(bound.variant_prompt_id)
        workflow = getattr(record, "workflow", None)
        if isinstance(workflow, dict):
            self._guidance.set_source(bound.variant_prompt_id, workflow, getattr(record, "surface_mode", None))
        self._vision.set_image(bound.variant_path)
        self._what_changed.set_voting_enabled(True)

    def _on_pair_failed(self, generation: int, message: str) -> None:
        if generation != self._pair_generation:
            return
        self._bound_pair = None
        self._what_changed.set_voting_enabled(False)
        self._guidance.note(f"Comparison unavailable: {message}")

    def _on_verdict_persisted(self):
        self._verdict_pending = False
        if self._bound_pair is not None:
            self._what_changed.set_voting_enabled(True)

    def _on_verdict_persist_failed(self, message: str) -> None:
        self._on_verdict_persisted()
        self._guidance.note(f"Could not save verdict: {message}")

    def advisor_trajectory(self):
        """Payload for the next advisor call (#750): trajectory, not just now."""
        from middleware.src.core.guidance_trajectory import format_for_advisor

        traj = self._what_changed.trajectory()
        return format_for_advisor(traj) if traj is not None else None

    def _on_guidance_verdict(self, _verdict: str) -> None:
        from middleware.src.core.guidance_pair import pair_matches_trajectory

        traj = self._what_changed.trajectory()
        bound = self._bound_pair
        if traj is None or bound is None:
            return
        if not pair_matches_trajectory(bound, traj, self._what_changed.variant_id()):
            return
        from functools import partial

        from middleware.src.core.guidance_trajectory import save_trajectory, trajectory_sidecar_path

        from gui.src.tabs.models.guidance_diff_widget import variant_workflow_dir

        path = trajectory_sidecar_path(
            self._guidance._variant_dir or variant_workflow_dir(), self._what_changed.variant_id()
        )
        self._verdict_pending = True
        self._what_changed.set_voting_enabled(False)
        self._pair_loader.persist(
            self._guidance._manager,
            traj,
            self._what_changed.variant_id(),
            partial(save_trajectory, path),
        )

    def _on_upscale(self) -> None:
        """Upscale the focused (first) compared image on the shared admission (#749)."""
        paths = list(getattr(self, "_compare_paths", ()))
        if not paths:
            self._upscale_status.setText("No output to upscale — pin an image first.")
            return
        self._upscale_btn.setEnabled(False)
        self._upscale_status.setText(f"Upscaling {os.path.basename(paths[0])}…")
        self._upscaler.start([paths[0]])

    def _on_upscale_finished(self, outputs) -> None:
        self._upscale_btn.setEnabled(True)
        if not outputs:
            self._upscale_status.setText("Upscale finished with no output.")
            return
        paths = list(getattr(self, "_compare_paths", ()))
        for path in outputs:
            if path not in paths:
                paths.append(path)
        self.set_compare_paths(paths)
        self._upscale_status.setText(f"Upscaled → {os.path.basename(outputs[-1])}")

    def _on_upscale_error(self, message: str) -> None:
        self._upscale_btn.setEnabled(True)
        self._upscale_status.setText(message)

    def _invalidate_suggestion(self):
        self._suggest_generation += 1
        self._suggest_context.clear()
        self._suggest_approve.setChecked(False)

    def _suggestion_key(self):
        from middleware.src.core.guidance_schema import workflow_hash
        return (
            self._guidance._source_id, workflow_hash(self._guidance._workflow),
            self._vision._generation, self._vision._image,
            self._vision._endpoint.text(), self._vision._model.text(), self._vision._note.text(),
            self._vision._placement.currentData(), repr(self.advisor_trajectory()), self._what_changed.feedback(),
        )

    def _approve_suggestion_payload(self, checked):
        self._suggest_approval_key = self._suggestion_key() if checked else None

    def suggest_from_workflow(self) -> None:
        """Request → parse → validate → Diff & Apply, using the captured workflow."""
        if self._suggest_closed.is_set() or self._guidance._busy or self._verdict_pending:
            self._guidance.note("Wait for the current variant before requesting suggestions.")
            return
        expected_variant = self._what_changed.variant_id()
        if expected_variant and (
            self._bound_pair is None or self._guidance._source_id != expected_variant
        ):
            self._guidance.note("Load the matching variant workflow and comparison before another suggestion.")
            return
        workflow = getattr(self._guidance, "_workflow", None)
        prompt_id = getattr(self._guidance, "_source_id", None)
        mode = getattr(self._guidance, "_source_mode", None)
        if not isinstance(workflow, dict):
            selection = self._host.generate_selection()
            if selection is None:
                self._guidance.note("Select a run in Generate's filmstrip first.")
                return
            prompt_id, workflow, mode = selection
            self._guidance.set_source(prompt_id, workflow, mode)
        image = self._vision._image
        if not image:
            self._guidance.note("Pin an image before asking for suggestions.")
            return
        if self._suggest_thread is not None and self._suggest_thread.is_alive():
            self._guidance.note("A suggestion is already running.")
            return
        vision_thread = getattr(self._vision, "_thread", None)
        if vision_thread is not None and vision_thread.is_alive():
            self._guidance.note("A review read is already running.")
            return
        leaves = self._vision._placement.currentData() == "cloud"
        approved = bool(self._vision._approve.isChecked())
        if leaves and not (self._vision._previewed and approved):
            self._guidance.note("Cloud analysis needs an explicit send approval.")
            return
        key = self._suggestion_key()
        if leaves and (not self._suggest_approve.isChecked() or self._suggest_approval_key != key):
            self._guidance.note("Approve sending workflow, OCR and history for this suggestion first.")
            return
        self._suggest_generation += 1
        self._suggest_context[self._suggest_generation] = (prompt_id, mode, key)
        snapshot = {
            "generation": self._suggest_generation,
            "workflow": deepcopy(workflow),
            "prompt_id": prompt_id,
            "mode": mode,
            "image": image,
            "note": self._vision._note.text() + "\nReview feedback: " + self._what_changed.feedback(),
            "trajectory": self.advisor_trajectory(),
            "approved": approved,
            "leaves": leaves,
            "placement": self._vision._placement.currentData(),
            "endpoint": self._vision._endpoint.text().strip(),
            "model": self._vision._model.text().strip(),
        }
        self._guidance.note("Requesting validated suggestions…")
        self._suggest_thread = threading.Thread(
            target=self._suggest_worker, args=(snapshot,), name="guidance-suggest", daemon=True,
        )
        self._suggest_thread.start()

    def _suggest_worker(self, snapshot: dict) -> None:
        from middleware.src.core.guidance_request import (
            GuidanceOutcome,
            build_guidance_request,
            interpret_guidance,
        )
        from middleware.src.core.guidance_vision import run_ocr, vlm_api_key_from_vault

        outcome: GuidanceOutcome | None = None
        error = ""
        try:
            ocr = run_ocr(self._vision._ocr, snapshot["image"])
            if self._suggest_closed.is_set() or snapshot["generation"] != self._suggest_generation:
                return
            ocr_text = None if ocr.unavailable else ocr.text
            request = build_guidance_request(
                workflow=snapshot["workflow"],
                note=snapshot["note"],
                ocr_text=ocr_text,
                trajectory=snapshot["trajectory"],
            )
            if snapshot["leaves"] and not snapshot["approved"]:
                outcome = GuidanceOutcome(
                    request, "", None, None, False, "Cloud analysis needs an explicit send approval.",
                )
            else:
                advisor = self._vision._advisor_for({
                    "placement": snapshot["placement"],
                    "endpoint": snapshot["endpoint"],
                    "model": snapshot["model"],
                    "api_key": vlm_api_key_from_vault(self._vision._vault) if snapshot["leaves"] else None,
                })
                if self._suggest_closed.is_set() or snapshot["generation"] != self._suggest_generation:
                    return
                reply = advisor.complete(
                    snapshot["image"], prompt=request.prompt, approved=snapshot["approved"],
                )
                if reply.unavailable:
                    outcome = GuidanceOutcome(request, "", None, None, False, reply.unavailable)
                else:
                    getter = getattr(self._guidance._manager, "get_object_info", None)
                    object_info = getter() if callable(getter) else None
                    outcome = interpret_guidance(
                        reply.text, snapshot["workflow"], request,
                        object_info=object_info if isinstance(object_info, dict) else None,
                    )
        except Exception as exc:
            error = str(exc)[:300]
        if snapshot["generation"] == self._suggest_generation and not self._suggest_closed.is_set():
            self._suggest_bus.finished.emit(snapshot["generation"], outcome, error)

    def _on_suggestion(self, generation: int, outcome, error: str) -> None:
        context = self._suggest_context.pop(generation, None)
        if context is None or self._suggest_closed.is_set():
            return
        prompt_id, mode, key = context
        if generation != self._suggest_generation or key != self._suggestion_key():
            return
        if error or outcome is None:
            self._guidance.note(error or "Suggestion failed.")
            return
        if outcome.validation is None:
            self._guidance.note(outcome.unavailable or "Advisor response was not valid guidance.")
            return
        self.show_guidance(
            workflow=outcome.request.workflow,
            validation=outcome.validation,
            source_prompt_id=prompt_id,
            source_mode=mode,
        )
        self._guidance.note(outcome.evidence_note())

    def show_guidance(self, *, workflow, validation, source_prompt_id=None, source_mode=None) -> None:
        """Render validated suggestions (#750/#753 produce these; #754 reads the outcome)."""
        self._guidance.set_guidance(
            workflow=workflow,
            validation=validation,
            source_prompt_id=source_prompt_id,
            source_mode=source_mode,
        )

    def _on_load_generate_selection(self) -> None:
        selection = self._host.generate_selection()
        if selection is None:
            self._guidance.note("Select a run in Generate's filmstrip first.")
            return
        if self._guidance._busy:
            self._guidance.note("Wait for the current variant before changing the source.")
            return
        self._invalidate_suggestion()
        self._invalidate_pair_load()
        self._what_changed.clear()
        prompt_id, workflow, mode = selection
        self._guidance.set_source(prompt_id, workflow, mode)
