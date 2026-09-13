"""Cloud Compute Offload window shell (§4.21, #488).

Hosts the multi-cloud compute offload management interface, structured with
a modern left-nav sidebar and QStackedWidget matching the SettingsWindow design.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.theme_api import qss

from ..window_manager import register_window
from .cloud_settings_pane import CloudSettingsPane
from .dashboards_pane import DashboardsPane
from .providers_pane import ProvidersPane
from .request_builder_pane import RequestBuilderPane


class CloudComputeWindow(QWidget):
    """Standalone window for Cloud Compute Offload management."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(None, Qt.WindowType.Window)
        register_window(self)
        self.main_window_ref = parent
        self.vault_manager = getattr(parent, "vault_manager", None) if parent else None

        self.setWindowTitle("Cloud Compute Offload")
        self.setMinimumSize(920, 640)
        self.resize(1000, 700)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header Bar ───────────────────────────────────────────────────────
        header_frame = QFrame()
        header_frame.setObjectName("cloud_header_frame")
        header_frame.setStyleSheet(qss("cloud_header_frame"))
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(18, 10, 18, 10)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        lbl_title = QLabel("Cloud Compute Offload")
        lbl_title.setStyleSheet(qss("cloud_window_title"))
        title_vbox.addWidget(lbl_title)

        lbl_subtitle = QLabel(
            "Dispatch heavy frame extraction, GIF transcoding, and deep-learning generation tasks to remote cloud workers (§4.21)"
        )
        lbl_subtitle.setStyleSheet(qss("cloud_window_subtitle"))
        title_vbox.addWidget(lbl_subtitle)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch(1)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(QSize(28, 28))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(qss("context_inspector_close_btn"))
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close)

        main_layout.addWidget(header_frame)

        # ── Body: Left-Nav Sidebar + Stacked Widget ──────────────────────────
        body_frame = QFrame()
        body_frame.setStyleSheet(qss("cloud_body_bg"))
        body_layout = QHBoxLayout(body_frame)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Left Sidebar Navigation
        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(210)
        self.nav_list.setStyleSheet(qss("cloud_nav_list"))

        nav_items = [
            ("☁️  Providers", "Overview and selection of target cloud platforms"),
            ("⚡  Request Builder", "Define, configure, and dispatch remote compute tasks"),
            ("📊  Dashboards", "Resource consumption, performance, and spend telemetry"),
            ("⚙️  Credentials & Config", "Vault-secured provider secrets and endpoints"),
        ]

        for text, tip in nav_items:
            item = QListWidgetItem(text)
            item.setToolTip(tip)
            self.nav_list.addItem(item)

        body_layout.addWidget(self.nav_list)

        # Right Stacked Pages
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(qss("cloud_body_bg"))

        self.pane_providers = ProvidersPane(parent=self)
        self.pane_request_builder = RequestBuilderPane(parent=self)
        self.pane_dashboards = DashboardsPane(parent=self)
        self.pane_settings = CloudSettingsPane(vault_manager=self.vault_manager, parent=self)

        self.stack.addWidget(self.pane_providers)
        self.stack.addWidget(self.pane_request_builder)
        self.stack.addWidget(self.pane_dashboards)
        self.stack.addWidget(self.pane_settings)

        body_layout.addWidget(self.stack)
        main_layout.addWidget(body_frame)

        # ── Bottom Status Bar ────────────────────────────────────────────────
        status_bar = QFrame()
        status_bar.setStyleSheet(qss("cloud_status_bar"))
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(14, 4, 14, 4)

        self.lbl_status = QLabel("Ready • Active Provider: Google Cloud Run (GCD) [us-central1]")
        self.lbl_status.setStyleSheet(qss("cloud_status_label"))
        status_layout.addWidget(self.lbl_status)
        status_layout.addStretch(1)

        lbl_vault_badge = QLabel("🔒 Vault Protected")
        lbl_vault_badge.setStyleSheet(qss("cloud_vault_badge"))
        status_layout.addWidget(lbl_vault_badge)

        main_layout.addWidget(status_bar)

        # ── Signal Connections ───────────────────────────────────────────────
        self.nav_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.pane_providers.active_provider_changed.connect(self._on_provider_changed)
        self.pane_request_builder.job_submitted.connect(self._on_job_submitted)

        # Select first nav item
        self.nav_list.setCurrentRow(0)

    def _on_provider_changed(self, provider_id: str) -> None:
        self.pane_request_builder.set_active_provider(provider_id)
        region = self.pane_providers.get_selected_region(provider_id)
        p_name = provider_id.upper()
        if provider_id == "gcd":
            p_name = "Google Cloud Run (GCD)"
        elif provider_id == "cloudflare":
            p_name = "Cloudflare Workers"
        elif provider_id == "oracle":
            p_name = "Oracle Cloud (OCI)"
        self.lbl_status.setText(f"Ready • Active Provider: {p_name} [{region}]")

    def _on_job_submitted(self, payload: dict) -> None:
        self.pane_dashboards.add_usage_row({
            "timestamp": payload.get("created_at", ""),
            "job_id": payload.get("job_id", ""),
            "provider": payload.get("provider", ""),
            "task": payload.get("task_type", ""),
            "duration": "In Flight",
            "egress": "~12.4 MB",
            "cost": "< $0.01",
        })
