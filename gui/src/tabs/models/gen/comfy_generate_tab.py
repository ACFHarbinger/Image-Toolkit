import contextlib
import json

from backend.src.comfy_matrix import gpu_lease
from backend.src.constants.comfy import ServerState
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.prompt_edit import PromptEdit
from gui.src.components.prompt_vocabulary import default_vocabulary
from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController

from ....theming.theme_api import qss
from ._comfy_bridge_sync import ComfyBridgeSyncMixin
from ._comfy_validation import ComfyValidationMixin
from .comfy_bridge import ComfyBridge
from .comfy_workflows import (  # noqa: F401  re-exported for callers and tests
    WORKFLOW_MODES,
    ImageUploadWorker,
    _load_workflow_template,
    _queue_workflow,
    build_workflow,
    plan_guided_workflow,
)


class ComfyUITab(ComfyValidationMixin, ComfyBridgeSyncMixin, QWidget):
    """
    Manages the ComfyUI server subprocess and opens its web UI in the system browser.
    """

    _log_signal = Signal(str)  # one log line
    _workflow_finished = Signal()


    def __init__(self, enable_manager=False, controller=None) -> None:
        super().__init__()
        self._controller = controller or ComfyWorkspaceController.instance()
        self._manager = self._controller.manager
        self.enable_manager = enable_manager
        # Pre-flight validation state (#738): per-mode issue lists, computed
        # from the manager's cached /object_info once the server is Ready.
        self._issues_by_mode: dict[str, list] = {}
        self._validation_pending = False
        self._validation_unavailable = False
        self._web_channel = None
        self._bridge: ComfyBridge | None = None
        self._syncing_param = False
        self._image_request = 0
        self._server_tokens: set[str] = set()
        self._local_to_token: dict[str, str] = {}
        self._token_to_local: dict[str, str] = {}
        self._init_ui()
        self._base_ckpt_edit.textChanged.connect(
            lambda _t: self._sync_guided_param_to_graph("checkpoint_node", "ckpt_name", self._base_ckpt_edit.text().strip())
        )
        self._extra_ckpt_edit.textChanged.connect(
            lambda _t: self._sync_guided_param_to_graph("extra_node", None, self._extra_ckpt_edit.text().strip())
        )
        self._prompt_edit.promptChanged.connect(
            lambda text: self._sync_guided_param_to_graph("positive_node", "text", text)
        )
        self._negative_prompt_edit.promptChanged.connect(
            lambda text: self._sync_guided_param_to_graph("negative_node", "text", text)
        )
        self._image_edit.textChanged.connect(
            lambda _t: self._sync_guided_param_to_graph("image_node", "image", self._image_edit.text().strip())
        )
        self._log_signal.connect(self._append_log)
        self._workflow_finished.connect(self._on_workflow_finished)
        self._controller.server_state_changed.connect(self._refresh_server)
        self._controller.busy_changed.connect(self._refresh_server)
        self._controller.log_line.connect(self._append_log)
        self._controller.error.connect(self._on_service_error)
        self._controller.object_info_changed.connect(self._on_object_info)
        self._refresh_server()
        if self._manager.get_object_info() is not None:
            self._on_object_info(self._manager.get_object_info())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.setContentsMargins(0, 0, 0, 0)
        lower_layout.setSpacing(8)

        # --- Server control bar ---
        ctrl_group = QGroupBox("ComfyUI Server")
        ctrl_layout = QHBoxLayout(ctrl_group)
        ctrl_layout.setContentsMargins(8, 6, 8, 6)

        self._start_btn = QPushButton("Start Server")
        self._start_btn.setFixedWidth(120)
        self._start_btn.setToolTip("Launch the ComfyUI HTTP server")
        self._start_btn.clicked.connect(self._on_start_clicked)
        ctrl_layout.addWidget(self._start_btn)
        self._connect_btn = QPushButton("Connect Existing")
        self._connect_btn.setToolTip("Connect to ComfyUI already running on the selected local port")
        self._connect_btn.clicked.connect(lambda: self._controller.connect(self._port_spin.value()))
        ctrl_layout.addWidget(self._connect_btn)

        self._stop_btn = QPushButton("Stop Server")
        self._stop_btn.setFixedWidth(120)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setToolTip("Shut down the ComfyUI HTTP server")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        ctrl_layout.addWidget(self._stop_btn)

        ctrl_layout.addWidget(QLabel("Port:"))
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(8188)
        self._port_spin.setFixedWidth(80)
        self._port_spin.setToolTip("TCP port (auto-increments if already in use)")
        ctrl_layout.addWidget(self._port_spin)

        ctrl_layout.addStretch()

        self._status_label = QLabel("Server: stopped")
        self._status_label.setStyleSheet(qss("comfy_status_label"))
        ctrl_layout.addWidget(self._status_label)

        lower_layout.addWidget(ctrl_group)

        # --- Open-in-browser panel ---
        browser_frame = QFrame()
        browser_frame.setFrameShape(QFrame.Shape.StyledPanel)
        browser_layout = QHBoxLayout(browser_frame)
        browser_layout.setContentsMargins(12, 8, 12, 8)

        self._url_label = QLabel("—")
        self._url_label.setStyleSheet(qss("comfy_url_label"))
        browser_layout.addWidget(self._url_label, stretch=1)

        self._open_btn = QPushButton("Open in External Browser")
        self._open_btn.setMinimumWidth(180)
        self._open_btn.setEnabled(False)
        self._open_btn.setToolTip(
            "Open the ComfyUI interface in your default web browser"
        )
        self._open_btn.clicked.connect(self._on_open_browser)
        browser_layout.addWidget(self._open_btn)

        root.addWidget(browser_frame)
        self._web_container = QWidget()
        self._web_container.setMinimumHeight(120)
        self._web_layout = QVBoxLayout(self._web_container)
        self._web_layout.setContentsMargins(0, 0, 0, 0)
        self._web_view = None
        tier_hint = QLabel("ComfyUI runs inside this tab while the server is ready. Open in External Browser stays available.")
        tier_hint.setWordWrap(True)
        lower_layout.addWidget(tier_hint)

        # --- ControlNet / IP-Adapter workflow panel (Content Gen §1.4) ---
        wf_group = QGroupBox("ControlNet / IP-Adapter Workflow")
        wf_layout = QVBoxLayout(wf_group)
        wf_layout.setContentsMargins(8, 6, 8, 6)
        wf_layout.setSpacing(4)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        for key, cfg in WORKFLOW_MODES.items():
            self._mode_combo.addItem(cfg["label"], key)
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo, stretch=1)
        wf_layout.addLayout(mode_row)

        ckpt_row = QHBoxLayout()
        ckpt_row.addWidget(QLabel("Base Checkpoint:"))
        self._base_ckpt_edit = QLineEdit("sd_xl_base_1.0.safetensors")
        self._base_ckpt_edit.setToolTip(
            "Must already exist under ComfyUI/models/checkpoints/. Not downloaded by this app."
        )
        self._base_ckpt_edit.textChanged.connect(lambda _t: self._on_validation_param_changed(all_modes=True))
        ckpt_row.addWidget(self._base_ckpt_edit, stretch=1)
        wf_layout.addLayout(ckpt_row)

        extra_ckpt_row = QHBoxLayout()
        self._extra_ckpt_label = QLabel()
        extra_ckpt_row.addWidget(self._extra_ckpt_label)
        self._extra_ckpt_edit = QLineEdit()
        self._extra_ckpt_edit.setToolTip(
            "ControlNet checkpoints go under ComfyUI/models/controlnet/, "
            "IP-Adapter checkpoints under ComfyUI/models/ipadapter/. "
            "Not downloaded by this app -- place the file yourself."
        )
        self._extra_ckpt_edit.textChanged.connect(lambda _t: self._on_validation_param_changed())
        extra_ckpt_row.addWidget(self._extra_ckpt_edit, stretch=1)
        wf_layout.addLayout(extra_ckpt_row)

        image_row = QHBoxLayout()
        self._image_label = QLabel()
        image_row.addWidget(self._image_label)
        self._image_edit = QLineEdit()
        self._image_edit.setToolTip(
            "Pre-processed control image (pose/depth/canny map) for ControlNet, "
            "or the reference image for IP-Adapter."
        )
        image_row.addWidget(self._image_edit, stretch=1)
        self._browse_btn = QPushButton("Browse…")
        self._browse_btn.setFixedWidth(90)
        self._browse_btn.clicked.connect(self._on_browse_image)
        image_row.addWidget(self._browse_btn)
        wf_layout.addLayout(image_row)

        prompt_row = QHBoxLayout()
        prompt_row.addWidget(QLabel("Prompt:"))
        self._prompt_edit = PromptEdit("masterpiece, best quality, anime coloring, 1girl, solo")
        self._prompt_edit.set_vocabulary(default_vocabulary())
        prompt_row.addWidget(self._prompt_edit, stretch=1)
        wf_layout.addLayout(prompt_row)

        neg_prompt_row = QHBoxLayout()
        neg_prompt_row.addWidget(QLabel("Negative Prompt:"))
        self._negative_prompt_edit = PromptEdit("lowres, worst quality, bad anatomy, bad hands")
        self._negative_prompt_edit.set_vocabulary(default_vocabulary())
        neg_prompt_row.addWidget(self._negative_prompt_edit, stretch=1)
        wf_layout.addLayout(neg_prompt_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Seed:"))
        self._seed_spin = QSpinBox()
        self._seed_spin.setRange(0, 2**31 - 1)
        self._seed_spin.setValue(0)
        self._seed_spin.setObjectName("comfy_guided_seed")
        size_row.addWidget(self._seed_spin)
        size_row.addWidget(QLabel("Width:"))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(64, 2048)
        self._width_spin.setSingleStep(64)
        self._width_spin.setValue(1024)
        self._width_spin.setObjectName("comfy_guided_width")
        size_row.addWidget(self._width_spin)
        size_row.addWidget(QLabel("Height:"))
        self._height_spin = QSpinBox()
        self._height_spin.setRange(64, 2048)
        self._height_spin.setSingleStep(64)
        self._height_spin.setValue(1024)
        self._height_spin.setObjectName("comfy_guided_height")
        size_row.addWidget(self._height_spin)
        size_row.addStretch()
        wf_layout.addLayout(size_row)

        queue_row = QHBoxLayout()
        queue_row.addStretch()
        self._validation_label = QLabel()
        self._validation_label.setToolTip(
            "Pre-flight check of the selected mode against the running ComfyUI server"
        )
        queue_row.addWidget(self._validation_label)
        self._queue_btn = QPushButton("Queue Workflow")
        self._queue_btn.setToolTip(
            "Upload the control/reference image and submit the curated workflow "
            "to the running ComfyUI server"
        )
        self._queue_btn.clicked.connect(self._on_queue_workflow_clicked)
        queue_row.addWidget(self._queue_btn)
        wf_layout.addLayout(queue_row)

        lower_layout.addWidget(wf_group)
        self._on_mode_changed(self._mode_combo.currentIndex())

        # --- Log panel ---
        log_group = QGroupBox("Server Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(6, 6, 6, 6)
        log_layout.setSpacing(4)

        log_btn_row = QHBoxLayout()
        log_btn_row.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self._log_view.clear())
        log_btn_row.addWidget(clear_btn)
        log_layout.addLayout(log_btn_row)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.document().setMaximumBlockCount(2000)
        self._log_view.setStyleSheet(qss("comfy_log_text"))
        log_layout.addWidget(self._log_view)

        lower_layout.addWidget(log_group, stretch=1)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._web_container)
        splitter.addWidget(lower)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([520, 380])
        root.addWidget(splitter, stretch=1)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_start_clicked(self) -> None:
        self._controller.start(self._port_spin.value(), self.enable_manager)

    def _on_stop_clicked(self) -> None:
        self._controller.stop()

    def _on_open_browser(self) -> None:
        if self._controller.open_external():
            gpu_lease.note_external_browser(True)
            self._append_log(f"[workflow] {gpu_lease.scope_text()}\n")

    def _refresh_server(self, *_args) -> None:
        state = self._controller.server_state
        if not isinstance(state, ServerState):
            state = ServerState.STOPPED
        busy = self._controller.busy
        ready = state == ServerState.READY
        active = state != ServerState.STOPPED
        self._start_btn.setEnabled(not busy and not active)
        self._connect_btn.setEnabled(not busy and not active)
        self._port_spin.setEnabled(not busy and not active)
        self._stop_btn.setEnabled(active or busy)
        self._stop_btn.setText("Stop Server" if self._manager.owns_server else "Disconnect")
        self._stop_btn.setToolTip(
            "Stop the server launched by Image Toolkit" if self._manager.owns_server
            else "Disconnect without stopping the external server"
        )
        self._open_btn.setEnabled(ready)
        self._url_label.setText(self._manager.url if active else "—")
        self._sync_web_view(ready)
        self._status_label.setText(f"Server: {state}")
        if ready:
            self._port_spin.setValue(self._manager.port)
            # /object_info is warmed off-thread at Ready; until it lands the
            # Queue button waits in its checking state.
            self._validation_pending = (
                not self._validation_unavailable
                and self._manager.get_object_info() is None
            )
        else:
            self._validation_pending = False
            self._validation_unavailable = False
            self._issues_by_mode = {}
        self._update_queue_state()

    @Slot(str)
    def _on_service_error(self, message: str) -> None:
        self._append_log(f"[comfy-manager] {message}\n")
        self._status_label.setText(message)

    @Slot()
    def _on_workflow_finished(self) -> None:
        self._update_queue_state()

    # ------------------------------------------------------------------
    # Pre-flight validation (#738)
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------
    # ControlNet / IP-Adapter workflow handlers (Content Gen §1.4)
    # ------------------------------------------------------------------

    def _on_mode_changed(self, _index: int) -> None:
        self._image_request += 1
        mode = self._mode_combo.currentData()
        cfg = WORKFLOW_MODES[mode]
        self._syncing_param = True
        self._extra_ckpt_label.setText(cfg["extra_label"])
        self._extra_ckpt_edit.setText(cfg["extra_default"])
        self._image_label.setText(cfg["image_label"])
        needs_image = bool(cfg.get("image_node"))
        self._image_edit.setEnabled(needs_image)
        self._browse_btn.setEnabled(needs_image)
        self._revalidate([mode])
        self._syncing_param = False
        self._sync_all_guided_params()

    def _on_browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self._image_edit.setText(path)

    def _on_queue_workflow_clicked(self) -> None:
        if self._controller.server_state != ServerState.READY:
            self._log_signal.emit(
                "[workflow] ComfyUI server is not running — start it first.\n"
            )
            return

        mode = self._mode_combo.currentData()
        image_path = self._image_edit.text().strip()
        if WORKFLOW_MODES[mode].get("image_node") and not image_path:
            self._log_signal.emit("[workflow] No control/reference image selected.\n")
            return
        base_checkpoint = self._base_ckpt_edit.text().strip()
        extra_checkpoint = self._extra_ckpt_edit.text().strip()
        positive_prompt = self._prompt_edit.text()
        negative_prompt = self._negative_prompt_edit.text()

        issues = self._issues_by_mode.get(mode)
        if issues:
            self._log_signal.emit(
                f"[workflow] Blocked by pre-flight validation: {issues[0].message}\n"
            )
            return

        manager = self._manager
        log = self._controller._publish_log
        seed = self._seed_spin.value()
        width = self._width_spin.value()
        height = self._height_spin.value()
        uploaded_image = self._local_to_token.get(image_path) or (image_path if image_path in self._server_tokens else None)
        args = (mode, image_path, base_checkpoint, extra_checkpoint, positive_prompt, negative_prompt)
        self._controller.run_http_action(
            lambda: _queue_workflow(
                manager, log, *args, seed=seed, width=width, height=height,
                cancel=self._controller._cancel, uploaded_image=uploaded_image,
            )
        )

    def _queue_workflow_worker(
        self,
        mode: str,
        image_path: str,
        base_checkpoint: str,
        extra_checkpoint: str,
        positive_prompt: str,
        negative_prompt: str,
    ) -> None:
        try:
            uploaded_image = self._local_to_token.get(image_path) or (image_path if image_path in self._server_tokens else None)
            _queue_workflow(
                self._manager, self._log_signal.emit, mode, image_path,
                base_checkpoint, extra_checkpoint, positive_prompt, negative_prompt,
                uploaded_image=uploaded_image,
            )
        finally:
            self._workflow_finished.emit()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(str)
    def _append_log(self, line: str) -> None:
        self._log_view.moveCursor(QTextCursor.MoveOperation.End)
        self._log_view.insertPlainText(line)
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        # The app-level controller owns the service, not this disposable view.
        self._unmount_web_view()
        super().closeEvent(event)

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

