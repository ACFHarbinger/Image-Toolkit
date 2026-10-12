import copy
import json
from pathlib import Path

from backend.src.constants.comfy import ServerState
from PySide6.QtCore import Signal, Slot
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.prompt_edit import PromptEdit
from gui.src.components.prompt_vocabulary import default_vocabulary
from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController

from ....theming.theme_api import qss

# #729's accepted v1 tier is external-only: the wallpaper application event
# filter still collides with WebEngine native QObject wrapping.

# Content Gen §1.4 (issue #35) — ControlNet + IP-Adapter workflow modes.
#
# Each mode maps to a curated workflow JSON template under
# configs/comfy_workflows/ plus the node ids that need overriding: the base
# checkpoint, positive/negative prompt text, the extra conditioning image
# (control image for ControlNet, reference image for IP-Adapter), and the
# extra model checkpoint (ControlNet or IP-Adapter weights). The three
# ControlNet sub-modes share one template and differ only in which
# preprocessor's control image / ControlNet checkpoint the user supplies.
WORKFLOW_MODES = {
    "controlnet_pose": {
        "label": "ControlNet — Pose (OpenPose)",
        "template": "controlnet_generate.json",
        "checkpoint_node": "1",
        "positive_node": "2",
        "negative_node": "3",
        "image_node": "9",
        "extra_node": "8",
        "extra_key": "control_net_name",
        "extra_default": "control_v11p_sd15_openpose.pth",
        "extra_label": "ControlNet Checkpoint:",
        "image_label": "Pose Control Image:",
    },
    "controlnet_depth": {
        "label": "ControlNet — Depth",
        "template": "controlnet_generate.json",
        "checkpoint_node": "1",
        "positive_node": "2",
        "negative_node": "3",
        "image_node": "9",
        "extra_node": "8",
        "extra_key": "control_net_name",
        "extra_default": "control_v11f1p_sd15_depth.pth",
        "extra_label": "ControlNet Checkpoint:",
        "image_label": "Depth Control Image:",
    },
    "controlnet_canny": {
        "label": "ControlNet — Canny",
        "template": "controlnet_generate.json",
        "checkpoint_node": "1",
        "positive_node": "2",
        "negative_node": "3",
        "image_node": "9",
        "extra_node": "8",
        "extra_key": "control_net_name",
        "extra_default": "control_v11p_sd15_canny.pth",
        "extra_label": "ControlNet Checkpoint:",
        "image_label": "Canny Control Image:",
    },
    "ipadapter_reference": {
        "label": "IP-Adapter — Reference Image",
        "template": "ipadapter_generate.json",
        "checkpoint_node": "1",
        "positive_node": "6",
        "negative_node": "7",
        "image_node": "4",
        "extra_node": "3",
        "extra_key": "ipadapter_file",
        "extra_default": "ip-adapter-plus_sdxl_vit-h.safetensors",
        "extra_label": "IP-Adapter Checkpoint:",
        "image_label": "Reference Image:",
    },
}


# Template loading/override-merging is duplicated here (a thin ~10-line
# mirror of ComfyUIManager.load_workflow()/apply_overrides()) rather than
# imported from backend.src.models.core.comfy_manager, because
# gui/test/conftest.py blanket-mocks that module for every GUI test (its
# "block heavy imports" convention, predating this change, applies to the
# whole models/core package). Keeping the pure template logic self-contained
# here means build_workflow() stays unit-testable without fighting that
# mock; the network calls (upload_image/queue_workflow) still go through
# self._manager, which individual tests mock per-instance as needed.
_WORKFLOWS_DIR = Path(__file__).resolve().parents[5] / "configs" / "comfy_workflows"


def _load_workflow_template(name: str) -> dict:
    with open(_WORKFLOWS_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def build_workflow(
    mode: str,
    *,
    base_checkpoint: str,
    extra_checkpoint: str,
    positive_prompt: str,
    negative_prompt: str,
    image_filename: str,
) -> dict:
    """Load the curated template for *mode* and apply the GUI's parameter
    overrides (base checkpoint, prompts, extra ControlNet/IP-Adapter
    checkpoint, and the uploaded extra-image filename).

    Pure function (no Qt / no network) so it can be exercised directly in
    tests without a running ComfyUI server or QApplication.
    """
    cfg = WORKFLOW_MODES[mode]
    workflow = copy.deepcopy(_load_workflow_template(cfg["template"]))
    overrides = {
        cfg["checkpoint_node"]: {"ckpt_name": base_checkpoint},
        cfg["positive_node"]: {"text": positive_prompt},
        cfg["negative_node"]: {"text": negative_prompt},
        cfg["image_node"]: {"image": image_filename},
        cfg["extra_node"]: {cfg["extra_key"]: extra_checkpoint},
    }
    for node_id, node_overrides in overrides.items():
        node = workflow.get(node_id)
        if node is None:
            continue
        node.setdefault("inputs", {}).update(node_overrides)
    return workflow


def _queue_workflow(
    manager, log, mode, image_path, base_checkpoint, extra_checkpoint,
    positive_prompt, negative_prompt,
) -> None:
    try:
        log(f"[workflow] Uploading {image_path}…\n")
        uploaded_name = manager.upload_image(image_path)

        workflow = build_workflow(
            mode,
            base_checkpoint=base_checkpoint,
            extra_checkpoint=extra_checkpoint,
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            image_filename=uploaded_name,
        )

        log(f"[workflow] Queuing {WORKFLOW_MODES[mode]['label']}…\n")
        prompt_id = manager.queue_workflow(workflow)
        log(f"[workflow] Queued — prompt_id={prompt_id}\n")
    except Exception as exc:
        log(f"[workflow] Error: {exc}\n")


class ComfyUITab(QWidget):
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
        self._init_ui()
        self._log_signal.connect(self._append_log)
        self._workflow_finished.connect(self._on_workflow_finished)
        self._controller.server_state_changed.connect(self._refresh_server)
        self._controller.busy_changed.connect(self._refresh_server)
        self._controller.log_line.connect(self._append_log)
        self._controller.error.connect(self._on_service_error)
        self._controller.object_info_changed.connect(self._on_object_info)
        self._refresh_server()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

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

        root.addWidget(ctrl_group)

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
        tier_hint = QLabel("ComfyUI opens in your system browser. Server controls remain available here.")
        tier_hint.setWordWrap(True)
        root.addWidget(tier_hint)

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

        root.addWidget(wf_group)
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

        root.addWidget(log_group, stretch=1)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_start_clicked(self) -> None:
        self._controller.start(self._port_spin.value(), self.enable_manager)

    def _on_stop_clicked(self) -> None:
        self._controller.stop()

    def _on_open_browser(self) -> None:
        self._controller.open_external()

    def _refresh_server(self, *_args) -> None:
        state = self._controller.server_state
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

    # ------------------------------------------------------------------
    # ControlNet / IP-Adapter workflow handlers (Content Gen §1.4)
    # ------------------------------------------------------------------

    def _on_mode_changed(self, _index: int) -> None:
        mode = self._mode_combo.currentData()
        cfg = WORKFLOW_MODES[mode]
        self._extra_ckpt_label.setText(cfg["extra_label"])
        self._extra_ckpt_edit.setText(cfg["extra_default"])
        self._image_label.setText(cfg["image_label"])
        self._revalidate([mode])

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

        image_path = self._image_edit.text().strip()
        if not image_path:
            self._log_signal.emit("[workflow] No control/reference image selected.\n")
            return

        mode = self._mode_combo.currentData()
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
        args = (mode, image_path, base_checkpoint, extra_checkpoint, positive_prompt, negative_prompt)
        self._controller.run_http_action(lambda: _queue_workflow(manager, log, *args))

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
            _queue_workflow(
                self._manager, self._log_signal.emit, mode, image_path,
                base_checkpoint, extra_checkpoint, positive_prompt, negative_prompt,
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
        super().closeEvent(event)
