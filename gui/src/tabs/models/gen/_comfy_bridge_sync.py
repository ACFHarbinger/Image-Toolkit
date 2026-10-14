"""Embedded ComfyUI view and QWebChannel bridge sync for ComfyUITab (#755)."""
import contextlib
import json
from pathlib import Path

from backend.src.constants.comfy import ServerState
from PySide6.QtCore import QUrl, Slot

from gui.src.helpers.worker_retention import retain_until_stopped

from .comfy_workflows import WORKFLOW_MODES, ImageUploadWorker, _load_workflow_template


class ComfyBridgeSyncMixin:
    """Methods ComfyUITab uses to mount the embedded view and sync it."""

    def highlight_node(self, node_id: str | int) -> bool:
        """Highlight node in embedded ComfyUI graph via QWebChannel (#755)."""
        if self._bridge is None:
            return False
        self._bridge.highlight_node(node_id)
        return True

    def _sync_guided_param_to_graph(self, mode_node_key: str, widget_key: str | None, value: object) -> None:
        if self._syncing_param or self._bridge is None:
            return
        mode = self._mode_combo.currentData()
        cfg = WORKFLOW_MODES.get(mode)
        if not cfg:
            return
        node_id = cfg.get(mode_node_key)
        if not node_id:
            return
        if widget_key is None:
            widget_key = cfg.get("extra_key")
        if not widget_key:
            return
        if widget_key == "image":
            self._handle_image_param_sync(str(node_id), str(value or "").strip())
            return
        self._bridge.sync_param(node_id, widget_key, value)

    def _handle_image_param_sync(self, node_id: str, image_path: str) -> None:
        self._image_request += 1
        if not image_path:
            return
        if image_path in self._local_to_token:
            token = self._local_to_token[image_path]
            self._bridge.set_image_node(node_id, token)
            return

        if Path(image_path).is_file():
            if not self._manager.is_running and self._controller.server_state != ServerState.READY:
                return

            worker = ImageUploadWorker(self._manager, image_path, str(node_id), self._image_request)
            worker.finished.connect(self._on_image_uploaded)
            worker.error.connect(self._on_image_upload_error)
            worker.start()
            retain_until_stopped(worker)
        elif image_path in self._server_tokens:
            self._bridge.set_image_node(node_id, image_path)

    @Slot(object)
    def _on_image_uploaded(self, result) -> None:
        if not result:
            return
        request, node_id, local_path, token = result
        if request != self._image_request or self._image_edit.text().strip() != local_path:
            return
        self._local_to_token[local_path] = token
        self._token_to_local[token] = local_path
        self._server_tokens.add(token)
        if self._bridge and self._bridge.is_ready:
            self._bridge.set_image_node(node_id, token)

    @Slot(object)
    def _on_image_upload_error(self, exc) -> None:
        self._append_log(f"[bridge] Image upload failed: {exc}\n")

    def _sync_all_guided_params(self) -> None:
        if self._bridge is None or not self._bridge.is_ready:
            return
        mode = self._mode_combo.currentData()
        cfg = WORKFLOW_MODES.get(mode)
        if not cfg:
            return
        self._bridge.bind_template(_load_workflow_template(cfg["template"]))

    @Slot(str, str, str)
    def _on_param_changed_from_graph(self, node_id: str, widget_name: str, raw_value: str) -> None:
        if self._syncing_param:
            return
        mode = self._mode_combo.currentData()
        cfg = WORKFLOW_MODES.get(mode)
        if not cfg:
            return
        self._syncing_param = True
        try:
            val = raw_value
            with contextlib.suppress(Exception):
                val = json.loads(raw_value)
            val_str = str(val) if not isinstance(val, str) else val

            if str(node_id) == str(cfg.get("checkpoint_node")) and widget_name.lower() == "ckpt_name":
                if self._base_ckpt_edit.text() != val_str:
                    self._base_ckpt_edit.setText(val_str)
            elif str(node_id) == str(cfg.get("positive_node")) and widget_name.lower() == "text":
                if self._prompt_edit.text() != val_str:
                    self._prompt_edit.setText(val_str)
            elif str(node_id) == str(cfg.get("negative_node")) and widget_name.lower() == "text":
                if self._negative_prompt_edit.text() != val_str:
                    self._negative_prompt_edit.setText(val_str)
            elif (
                cfg.get("extra_node")
                and str(node_id) == str(cfg.get("extra_node"))
                and widget_name.lower() == str(cfg.get("extra_key", "")).lower()
                and self._extra_ckpt_edit.text() != val_str
            ):
                self._extra_ckpt_edit.setText(val_str)
            elif (
                cfg.get("image_node")
                and str(node_id) == str(cfg.get("image_node"))
                and widget_name.lower() == "image"
            ):
                self._image_request += 1
                self._server_tokens.add(val_str)
                local_path = self._token_to_local.get(val_str, val_str)
                if self._image_edit.text() != local_path:
                    self._image_edit.setText(local_path)
        finally:
            self._syncing_param = False

    def _sync_web_view(self, ready: bool) -> None:
        if ready and self._web_view is None:
            self._mount_web_view()
        elif not ready and self._web_view is not None:
            self._unmount_web_view()

    def _mount_web_view(self) -> None:
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView

            from .comfy_bridge import setup_comfy_web_channel
        except ImportError:
            self._append_log("[workflow] Embedded view unavailable; use Open in External Browser.\n")
            return
        view = QWebEngineView(self._web_container)
        self._web_layout.addWidget(view)
        try:
            self._web_channel, self._bridge = setup_comfy_web_channel(view, allowed_url=self._manager.url)
            self._bridge.param_changed_in_graph.connect(self._on_param_changed_from_graph)
            self._bridge.bridge_ready.connect(self._sync_all_guided_params)
            self._bridge.log_message.connect(lambda msg: self._append_log(f"[bridge] {msg}\n"))
        except Exception as exc:
            self._append_log(f"[bridge] Channel setup error: {exc}\n")
        view.load(QUrl(self._manager.url))
        self._web_view = view
        with contextlib.suppress(Exception):
            from backend.src.comfy_matrix import gpu_lease
            if hasattr(gpu_lease, "note_embedded_view"):
                gpu_lease.note_embedded_view(str(id(self)), True)

    def _unmount_web_view(self) -> None:
        self._image_request += 1
        self._local_to_token.clear()
        self._token_to_local.clear()
        self._server_tokens.clear()
        view = self._web_view
        self._web_view = None
        with contextlib.suppress(Exception):
            from backend.src.comfy_matrix import gpu_lease
            if hasattr(gpu_lease, "note_embedded_view"):
                gpu_lease.note_embedded_view(str(id(self)), False)
        if self._web_channel is not None and self._bridge is not None:
            with contextlib.suppress(Exception):
                self._web_channel.deregisterObject(self._bridge)
            self._web_channel = None
        self._bridge = None
        if view is not None:
            self._web_layout.removeWidget(view)
            view.stop()
            page = view.page()
            if page is not None:
                with contextlib.suppress(Exception):
                    page.setWebChannel(None)
            import shiboken6

            if shiboken6.isValid(view):
                shiboken6.delete(view)
