import copy
import json
import threading
from pathlib import Path

from backend.src.models.core.comfy_manager import ComfyUIManager
from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QTextCursor
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

# QWebEngineView is intentionally NOT used here.
# Chromium (QtWebEngine) loads native libstdc++ via Vulkan/GBM at first render,
# which causes an RTTI __dynamic_cast SIGSEGV when JPype's JVM is already running
# in the same process — identical to the GTK/QFileDialog crash. The URL is opened
# in the system browser instead, which has no in-process library conflict.


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


class ComfyUITab(QWidget):
    """
    Manages the ComfyUI server subprocess and opens its web UI in the system browser.
    """

    _status_signal = Signal(str, str)  # (text, css-colour)
    _server_ready_signal = Signal(str)  # server URL
    _log_signal = Signal(str)  # one log line

    def __init__(self, enable_manager=False) -> None:
        super().__init__()
        self._manager = ComfyUIManager.instance()
        self.enable_manager = enable_manager
        self._log_thread: threading.Thread | None = None
        self._init_ui()
        self._status_signal.connect(self._on_status)
        self._server_ready_signal.connect(self._on_server_ready)
        self._log_signal.connect(self._append_log)

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
        self._status_label.setStyleSheet("color: #aaaaaa;")
        ctrl_layout.addWidget(self._status_label)

        root.addWidget(ctrl_group)

        # --- Open-in-browser panel ---
        browser_frame = QFrame()
        browser_frame.setFrameShape(QFrame.Shape.StyledPanel)
        browser_layout = QHBoxLayout(browser_frame)
        browser_layout.setContentsMargins(12, 8, 12, 8)

        self._url_label = QLabel("—")
        self._url_label.setStyleSheet("color: #aaaaaa; font-family: monospace;")
        browser_layout.addWidget(self._url_label, stretch=1)

        self._open_btn = QPushButton("Open in Browser")
        self._open_btn.setFixedWidth(140)
        self._open_btn.setEnabled(False)
        self._open_btn.setToolTip(
            "Open the ComfyUI interface in your default web browser"
        )
        self._open_btn.clicked.connect(self._on_open_browser)
        browser_layout.addWidget(self._open_btn)

        root.addWidget(browser_frame)

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
        self._prompt_edit = QLineEdit("masterpiece, best quality, anime coloring, 1girl, solo")
        prompt_row.addWidget(self._prompt_edit, stretch=1)
        wf_layout.addLayout(prompt_row)

        neg_prompt_row = QHBoxLayout()
        neg_prompt_row.addWidget(QLabel("Negative Prompt:"))
        self._negative_prompt_edit = QLineEdit("lowres, worst quality, bad anatomy, bad hands")
        neg_prompt_row.addWidget(self._negative_prompt_edit, stretch=1)
        wf_layout.addLayout(neg_prompt_row)

        queue_row = QHBoxLayout()
        queue_row.addStretch()
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
        self._log_view.setStyleSheet(
            "font-family: monospace; font-size: 9pt;"
        )
        log_layout.addWidget(self._log_view)

        root.addWidget(log_group, stretch=1)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_start_clicked(self) -> None:
        self._start_btn.setEnabled(False)
        self._port_spin.setEnabled(False)
        self._open_btn.setEnabled(False)
        self._log_view.clear()
        self._status_signal.emit("Starting…", "#f0ad4e")
        port = self._port_spin.value()
        threading.Thread(
            target=self._start_worker, args=(port, self.enable_manager), daemon=True
        ).start()

    def _on_stop_clicked(self) -> None:
        self._manager.stop()
        self._stop_btn.setEnabled(False)
        self._open_btn.setEnabled(False)
        self._start_btn.setEnabled(True)
        self._port_spin.setEnabled(True)
        self._url_label.setText("—")
        self._url_label.setStyleSheet("color: #aaaaaa; font-family: monospace;")
        self._status_signal.emit("Server: stopped", "#aaaaaa")

    def _on_open_browser(self) -> None:
        QDesktopServices.openUrl(QUrl(self._manager.url))

    # ------------------------------------------------------------------
    # ControlNet / IP-Adapter workflow handlers (Content Gen §1.4)
    # ------------------------------------------------------------------

    def _on_mode_changed(self, _index: int) -> None:
        mode = self._mode_combo.currentData()
        cfg = WORKFLOW_MODES[mode]
        self._extra_ckpt_label.setText(cfg["extra_label"])
        self._extra_ckpt_edit.setText(cfg["extra_default"])
        self._image_label.setText(cfg["image_label"])

    def _on_browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self._image_edit.setText(path)

    def _on_queue_workflow_clicked(self) -> None:
        if not self._manager.is_running:
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

        self._queue_btn.setEnabled(False)
        threading.Thread(
            target=self._queue_workflow_worker,
            args=(
                mode,
                image_path,
                base_checkpoint,
                extra_checkpoint,
                positive_prompt,
                negative_prompt,
            ),
            daemon=True,
        ).start()

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
            self._log_signal.emit(f"[workflow] Uploading {image_path}…\n")
            uploaded_name = self._manager.upload_image(image_path)

            workflow = build_workflow(
                mode,
                base_checkpoint=base_checkpoint,
                extra_checkpoint=extra_checkpoint,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                image_filename=uploaded_name,
            )

            self._log_signal.emit(f"[workflow] Queuing {WORKFLOW_MODES[mode]['label']}…\n")
            prompt_id = self._manager.queue_workflow(workflow)
            self._log_signal.emit(f"[workflow] Queued — prompt_id={prompt_id}\n")
        except Exception as exc:
            self._log_signal.emit(f"[workflow] Error: {exc}\n")
        finally:
            self._queue_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Background workers
    # ------------------------------------------------------------------

    def _start_worker(self, port: int, enable_manager: bool = False) -> None:
        try:
            actual_port = self._manager.start(port, enable_manager=enable_manager)
            self._log_signal.emit(f"[comfy-manager] Starting on port {actual_port}…\n")

            self._log_thread = threading.Thread(target=self._stream_logs, daemon=True)
            self._log_thread.start()

            ready = self._manager.wait_until_ready(timeout=120.0)
            if ready:
                self._server_ready_signal.emit(self._manager.url)
            else:
                self._status_signal.emit(
                    "Timed out — check the log for errors", "#d9534f"
                )
                self._start_btn.setEnabled(True)
                self._port_spin.setEnabled(True)
        except Exception as exc:
            self._status_signal.emit(f"Error: {exc}", "#d9534f")
            self._log_signal.emit(f"[comfy-manager] {exc}\n")
            self._start_btn.setEnabled(True)
            self._port_spin.setEnabled(True)

    def _stream_logs(self) -> None:
        for line in self._manager.iter_log_lines():
            self._log_signal.emit(line)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(str, str)
    def _on_status(self, text: str, colour: str) -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {colour};")

    @Slot(str)
    def _on_server_ready(self, url: str) -> None:
        self._stop_btn.setEnabled(True)
        self._open_btn.setEnabled(True)
        self._url_label.setText(url)
        self._url_label.setStyleSheet(
            "color: #5cb85c; font-family: monospace; font-weight: bold;"
        )
        self._status_signal.emit(f"Running at {url}", "#5cb85c")

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
        self._manager.stop()
        super().closeEvent(event)
