"""Workflow preflight validation and queue-button state for ComfyUITab."""
from middleware.src.constants.comfy import ServerState

from .comfy_workflows import (  # noqa: F401  re-exported for callers and tests
    WORKFLOW_MODES,
    ImageUploadWorker,
    _load_workflow_template,
    _queue_workflow,
    build_workflow,
    plan_guided_workflow,
)


class ComfyValidationMixin:
    """Workflow preflight validation and queue-button state for ComfyUITab."""

    def _workflow_for_mode(self, mode: str) -> dict:
        cfg = WORKFLOW_MODES[mode]
        # Only the current mode reads the live extra-checkpoint field; other
        # modes validate against their defaults (switching modes revalidates).
        extra = (self._extra_ckpt_edit.text().strip()
                 if mode == self._mode_combo.currentData()
                 else cfg["extra_default"])
        return build_workflow(
            mode,
            base_checkpoint=self._base_ckpt_edit.text().strip(),
            extra_checkpoint=extra,
            positive_prompt="",
            negative_prompt="",
            image_filename="placeholder.png",
        )

    def _revalidate(self, modes: list[str]) -> None:
        if self._controller.server_state != ServerState.READY:
            return
        if self._manager.get_object_info() is None:
            return  # warmup still in flight; object_info_changed retriggers
        for mode in modes:
            try:
                self._issues_by_mode[mode] = list(
                    self._manager.validate_template(self._workflow_for_mode(mode))
                )
            except RuntimeError:
                self._validation_unavailable = True
                self._issues_by_mode = {}
                break
        self._update_queue_state()

    def _on_validation_param_changed(self, *, all_modes: bool = False) -> None:
        if self._controller.server_state != ServerState.READY:
            return
        self._revalidate(list(WORKFLOW_MODES) if all_modes else [self._mode_combo.currentData()])

    def _on_object_info(self, info) -> None:
        self._validation_pending = False
        if info is None:
            # Fetch failed after retries: keep Queue usable (status quo ante)
            # and say so, rather than blocking generation on a hiccup.
            self._validation_unavailable = True
            self._issues_by_mode = {}
            self._append_log(
                "[workflow] Pre-flight validation unavailable: "
                "/object_info did not respond.\n"
            )
        else:
            self._validation_unavailable = False
            self._revalidate(list(WORKFLOW_MODES))
        self._update_queue_state()

    def _update_queue_state(self) -> None:
        mode = self._mode_combo.currentData()
        ready = (self._controller.server_state == ServerState.READY
                 and not self._controller.busy)
        if not ready:
            self._queue_btn.setEnabled(False)
            self._validation_label.setText("")
            return
        issues = self._issues_by_mode.get(mode, [])
        if self._validation_pending:
            self._queue_btn.setEnabled(False)
            self._validation_label.setText("Checking workflow compatibility…")
            return
        if issues:
            self._queue_btn.setEnabled(False)
            text = issues[0].message
            if len(issues) > 1:
                text += f" (+{len(issues) - 1} more)"
            self._validation_label.setText(text)
            self._queue_btn.setToolTip("\n".join(issue.message for issue in issues))
            return
        self._queue_btn.setEnabled(True)
        self._validation_label.setText("" if self._validation_unavailable else "Ready")
        self._queue_btn.setToolTip(
            "Upload the control/reference image and submit the curated workflow "
            "to the running ComfyUI server"
        )
