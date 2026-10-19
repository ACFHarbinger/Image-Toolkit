"""Embedded ComfyUI view and QWebChannel bridge sync for ComfyUITab (#755)."""
import contextlib
from pathlib import Path

from middleware.src.constants.comfy import ServerState
from PySide6.QtCore import QUrl

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


    def load_mode_template_into_canvas(self, mode: str | None = None) -> bool:
        """Load curated workflow template into embedded ComfyUI canvas (#755)."""
        if self._bridge is None or not self._bridge.is_ready:
            return False
        selected_mode = mode or self._mode_combo.currentData()
        cfg = WORKFLOW_MODES.get(selected_mode)
        if not cfg:
            return False
        template = _load_workflow_template(cfg["template"])
        self._bridge.load_template(template)
        self._append_log(f"[bridge] Loading '{cfg['label']}' template into canvas…\n")
        return True

    def _sync_all_guided_params(self) -> None:
        if self._bridge is None or not self._bridge.is_ready:
            return
        mode = self._mode_combo.currentData()
        cfg = WORKFLOW_MODES.get(mode)
        if not cfg:
            return
        self._bridge.bind_template(_load_workflow_template(cfg["template"]))


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
            self._bridge.template_loaded.connect(self._on_template_loaded)
            self._bridge.log_message.connect(lambda msg: self._append_log(f"[bridge] {msg}\n"))
        except Exception as exc:
            self._append_log(f"[bridge] Channel setup error: {exc}\n")
        view.load(QUrl(self._manager.url))
        self._web_view = view
        with contextlib.suppress(Exception):
            from middleware.src.comfy_matrix import gpu_lease
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
            from middleware.src.comfy_matrix import gpu_lease
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
