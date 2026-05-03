import threading

from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSpinBox,
    QGroupBox,
    QTextEdit,
    QFrame,
)

from backend.src.models.comfy_manager import ComfyUIManager

# QWebEngineView is intentionally NOT used here.
# Chromium (QtWebEngine) loads native libstdc++ via Vulkan/GBM at first render,
# which causes an RTTI __dynamic_cast SIGSEGV when JPype's JVM is already running
# in the same process — identical to the GTK/QFileDialog crash. The URL is opened
# in the system browser instead, which has no in-process library conflict.


class ComfyUITab(QWidget):
    """
    Manages the ComfyUI server subprocess and opens its web UI in the system browser.
    """

    _status_signal = Signal(str, str)   # (text, css-colour)
    _server_ready_signal = Signal(str)  # server URL
    _log_signal = Signal(str)           # one log line

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
        browser_frame.setFrameShape(QFrame.StyledPanel)
        browser_layout = QHBoxLayout(browser_frame)
        browser_layout.setContentsMargins(12, 8, 12, 8)

        self._url_label = QLabel("—")
        self._url_label.setStyleSheet("color: #aaaaaa; font-family: monospace;")
        browser_layout.addWidget(self._url_label, stretch=1)

        self._open_btn = QPushButton("Open in Browser")
        self._open_btn.setFixedWidth(140)
        self._open_btn.setEnabled(False)
        self._open_btn.setToolTip("Open the ComfyUI interface in your default web browser")
        self._open_btn.clicked.connect(self._on_open_browser)
        browser_layout.addWidget(self._open_btn)

        root.addWidget(browser_frame)

        # --- Log panel ---
        log_group = QGroupBox("Server Log")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(6, 6, 6, 6)
        log_layout.setSpacing(4)

        log_btn_row = QHBoxLayout()
        log_btn_row.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(60)
        clear_btn.clicked.connect(lambda: self._log_view.clear())
        log_btn_row.addWidget(clear_btn)
        log_layout.addLayout(log_btn_row)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setStyleSheet(
            "background: #1e1e1e; color: #d4d4d4;"
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
        threading.Thread(target=self._start_worker, args=(port, self.enable_manager), daemon=True).start()

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
    # Background workers
    # ------------------------------------------------------------------

    def _start_worker(self, port: int, enable_manager: bool = False) -> None:
        try:
            actual_port = self._manager.start(port, enable_manager=enable_manager)
            self._log_signal.emit(f"[comfy-manager] Starting on port {actual_port}…\n")

            self._log_thread = threading.Thread(
                target=self._stream_logs, daemon=True
            )
            self._log_thread.start()

            ready = self._manager.wait_until_ready(timeout=120.0)
            if ready:
                self._server_ready_signal.emit(self._manager.url)
            else:
                self._status_signal.emit("Timed out — check the log for errors", "#d9534f")
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
