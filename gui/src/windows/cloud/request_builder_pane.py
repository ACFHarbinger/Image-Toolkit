"""Request Builder pane for Cloud Compute Offload window (§4.21, #488).

Provides task definition (extraction range, resolution, framerate, prompt),
compute shape selection, upload privacy warnings, and live job queue status.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class RequestBuilderPane(QWidget):
    """Pane for constructing and submitting cloud compute offload jobs."""

    job_submitted = Signal(dict)  # Emits job payload dictionary

    def __init__(self, active_provider: str = "gcd", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._active_provider = active_provider
        self._jobs: list[Dict[str, Any]] = []

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # ── Section 1: Task Type & Source ────────────────────────────────────
        group_task = QGroupBox("1. Task Specification")
        group_task.setStyleSheet("QGroupBox { font-weight: bold; color: #f0f6fc; }")
        task_layout = QFormLayout(group_task)
        task_layout.setContentsMargins(14, 14, 14, 14)
        task_layout.setSpacing(10)

        self.combo_task_type = QComboBox()
        self.combo_task_type.addItems([
            "Frame Range Extraction",
            "Single Frame Snapshot",
            "GIF Animation Transcode",
            "Video Clip Slicing",
            "Deep Learning Image Generation",
        ])
        task_layout.addRow("Task Type:", self.combo_task_type)

        source_layout = QHBoxLayout()
        self.input_source_path = QLineEdit()
        self.input_source_path.setPlaceholderText("Select video or media file path...")
        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_source_file)
        source_layout.addWidget(self.input_source_path)
        source_layout.addWidget(self.btn_browse)
        task_layout.addRow("Source Media:", source_layout)

        # Extraction Range
        range_layout = QHBoxLayout()
        self.spin_start_ms = QSpinBox()
        self.spin_start_ms.setRange(0, 86400000)
        self.spin_start_ms.setSuffix(" ms")
        self.spin_end_ms = QSpinBox()
        self.spin_end_ms.setRange(0, 86400000)
        self.spin_end_ms.setSuffix(" ms")
        self.spin_end_ms.setValue(5000)
        range_layout.addWidget(QLabel("Start:"))
        range_layout.addWidget(self.spin_start_ms)
        range_layout.addWidget(QLabel("End:"))
        range_layout.addWidget(self.spin_end_ms)
        task_layout.addRow("Time Range:", range_layout)

        # Resolution & Framerate
        res_layout = QHBoxLayout()
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["Native", "1920x1080 (1080p)", "1280x720 (720p)", "854x480 (480p)", "Vertical (9:16)"])
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 120)
        self.spin_fps.setValue(24)
        self.spin_fps.setSuffix(" fps")
        res_layout.addWidget(QLabel("Resolution:"))
        res_layout.addWidget(self.combo_resolution)
        res_layout.addWidget(QLabel("Framerate:"))
        res_layout.addWidget(self.spin_fps)
        task_layout.addRow("Output Format:", res_layout)

        layout.addWidget(group_task)

        # ── Section 2: Cloud Shape & Execution ───────────────────────────────
        group_shape = QGroupBox("2. Remote Compute Environment")
        group_shape.setStyleSheet("QGroupBox { font-weight: bold; color: #f0f6fc; }")
        shape_layout = QFormLayout(group_shape)
        shape_layout.setContentsMargins(14, 14, 14, 14)
        shape_layout.setSpacing(10)

        self.lbl_target_provider = QLabel(f"Target Provider: <b>{self._active_provider.upper()}</b>")
        self.lbl_target_provider.setStyleSheet("color: #79c0ff; font-size: 9.5pt;")
        shape_layout.addRow(self.lbl_target_provider)

        self.combo_compute_shape = QComboBox()
        self.combo_compute_shape.addItems([
            "Standard (4 vCPU, 16 GiB RAM) [Recommended for Extraction]",
            "High-Memory (8 vCPU, 32 GiB RAM)",
            "GPU Accelerated (1x NVIDIA L4 / A10 Tensor Core)",
        ])
        shape_layout.addRow("Compute Shape:", self.combo_compute_shape)

        layout.addWidget(group_shape)

        # ── Section 3: Privacy & Actions ─────────────────────────────────────
        privacy_frame = QFrame()
        privacy_frame.setStyleSheet(
            "background-color: #161b22; border: 1px solid #d29922; border-radius: 6px;"
        )
        privacy_layout = QHBoxLayout(privacy_frame)
        privacy_layout.setContentsMargins(12, 8, 12, 8)
        lbl_warn = QLabel("⚠️ <b>Privacy Notice:</b> Source inputs will be packaged and uploaded over TLS to the selected cloud worker for remote processing.")
        lbl_warn.setStyleSheet("color: #e3b341; font-size: 8.5pt;")
        lbl_warn.setWordWrap(True)
        privacy_layout.addWidget(lbl_warn)
        layout.addWidget(privacy_frame)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_run_cloud = QPushButton("🚀 Run in Cloud")
        self.btn_run_cloud.setStyleSheet(
            "QPushButton { background-color: #238636; color: white; font-weight: bold; "
            "border-radius: 6px; padding: 8px 18px; font-size: 10pt; }"
            "QPushButton:hover { background-color: #2ea043; }"
        )
        self.btn_run_cloud.clicked.connect(self._on_run_cloud_clicked)
        btn_layout.addWidget(self.btn_run_cloud)

        self.btn_export_json = QPushButton("📋 Export Job JSON")
        self.btn_export_json.setStyleSheet(
            "QPushButton { background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 8px 14px; font-size: 9pt; }"
            "QPushButton:hover { background-color: #30363d; color: #f0f6fc; }"
        )
        self.btn_export_json.clicked.connect(self._on_export_json_clicked)
        btn_layout.addWidget(self.btn_export_json)

        btn_layout.addStretch(1)

        self.btn_reset = QPushButton("Reset Form")
        self.btn_reset.setStyleSheet(
            "QPushButton { background-color: transparent; color: #8b949e; border: 1px solid #30363d; "
            "border-radius: 6px; padding: 8px 12px; font-size: 8.5pt; }"
            "QPushButton:hover { color: #f0f6fc; border-color: #8b949e; }"
        )
        self.btn_reset.clicked.connect(self._on_reset_clicked)
        btn_layout.addWidget(self.btn_reset)

        layout.addLayout(btn_layout)

        # ── Section 4: Live Cloud Queue Status ───────────────────────────────
        group_queue = QGroupBox("3. Cloud Job Queue & Activity")
        group_queue.setStyleSheet("QGroupBox { font-weight: bold; color: #f0f6fc; }")
        queue_layout = QVBoxLayout(group_queue)
        queue_layout.setContentsMargins(12, 12, 12, 12)

        self.table_jobs = QTableWidget(0, 5)
        self.table_jobs.setHorizontalHeaderLabels(["Job ID", "Task", "Provider", "Status", "Timestamp"])
        self.table_jobs.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_jobs.setStyleSheet(
            "QTableWidget { background-color: #0d1117; border: 1px solid #30363d; "
            "color: #c9d1d9; gridline-color: #21262d; }"
            "QHeaderView::section { background-color: #161b22; color: #8b949e; font-weight: bold; padding: 4px; }"
        )
        self.table_jobs.setMinimumHeight(140)
        queue_layout.addWidget(self.table_jobs)

        layout.addWidget(group_queue)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def set_active_provider(self, provider_id: str) -> None:
        self._active_provider = provider_id
        self.lbl_target_provider.setText(f"Target Provider: <b>{provider_id.upper()}</b>")

    def _browse_source_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Source Video / Media", "", "Media Files (*.mp4 *.mkv *.webm *.mov *.avi *.png *.jpg);;All Files (*)"
        )
        if path:
            self.input_source_path.setText(path)

    def build_job_payload(self) -> Dict[str, Any]:
        """Construct the canonical JSON job specification payload."""
        job_id = f"job-{int(time.time() * 1000)}"
        return {
            "job_id": job_id,
            "provider": self._active_provider,
            "task_type": self.combo_task_type.currentText(),
            "source_path": self.input_source_path.text().strip(),
            "start_ms": self.spin_start_ms.value(),
            "end_ms": self.spin_end_ms.value(),
            "resolution": self.combo_resolution.currentText(),
            "fps": self.spin_fps.value(),
            "compute_shape": self.combo_compute_shape.currentText(),
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "QUEUED",
        }

    def _on_run_cloud_clicked(self) -> None:
        payload = self.build_job_payload()
        if not payload["source_path"]:
            QMessageBox.warning(self, "Missing Source", "Please select a source media file before dispatching.")
            return

        self._jobs.append(payload)
        row = self.table_jobs.rowCount()
        self.table_jobs.insertRow(row)
        self.table_jobs.setItem(row, 0, QTableWidgetItem(payload["job_id"]))
        self.table_jobs.setItem(row, 1, QTableWidgetItem(payload["task_type"]))
        self.table_jobs.setItem(row, 2, QTableWidgetItem(payload["provider"].upper()))
        self.table_jobs.setItem(row, 3, QTableWidgetItem("DISPATCHED"))
        self.table_jobs.setItem(row, 4, QTableWidgetItem(payload["created_at"]))

        self.job_submitted.emit(payload)
        QMessageBox.information(
            self,
            "Job Dispatched",
            f"Cloud job {payload['job_id']} packaged and dispatched to {payload['provider'].upper()}.\n"
            "Monitor progress in the queue table below.",
        )

    def _on_export_json_clicked(self) -> None:
        payload = self.build_job_payload()
        json_str = json.dumps(payload, indent=2)
        QMessageBox.information(self, "Job JSON Payload", json_str)

    def _on_reset_clicked(self) -> None:
        self.input_source_path.clear()
        self.spin_start_ms.setValue(0)
        self.spin_end_ms.setValue(5000)
        self.combo_resolution.setCurrentIndex(0)
        self.spin_fps.setValue(24)
