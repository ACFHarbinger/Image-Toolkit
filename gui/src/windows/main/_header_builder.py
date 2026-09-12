"""Application header widget: title, theme toggle, and settings buttons.

Extracted from ``MainWindow.__init__`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStyle, QWidget

from gui.src.theming.theme_api import qss


class _HeaderBuilderMixin:
    """Builds the top header bar and wires the theme/settings buttons."""

    def _build_header(self, account_name: str, app_icon) -> QWidget:
        header_widget = QWidget()
        header_widget.setObjectName("header_widget")
        header_widget.setStyleSheet(qss("main_header"))
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)

        self.title_label = QLabel(f"Image Database and Toolkit - {account_name}")
        self.title_label.setStyleSheet(qss("main_header_title"))
        header_layout.addWidget(self.title_label)
        header_layout.addStretch(1)

        # --- Theme toggle button (§3.10 / 2.8A) ---
        self._theme_toggle_btn = QPushButton()
        self._theme_toggle_btn.setFixedSize(QSize(36, 36))
        self._theme_toggle_btn.setObjectName("theme_toggle_button")
        self._theme_toggle_btn.setToolTip("Toggle dark / light theme")
        self._theme_toggle_btn.setStyleSheet(
            qss("main_icon_btn", OBJECT_NAME="theme_toggle_button")
        )
        self._theme_toggle_btn.clicked.connect(self._toggle_theme)
        header_layout.addWidget(self._theme_toggle_btn)

        # --- Cloud Compute button (§4.21) ---
        self.cloud_compute_button = QPushButton("☁️")
        self.cloud_compute_button.setFixedSize(QSize(36, 36))
        self.cloud_compute_button.setObjectName("cloud_compute_button")
        self.cloud_compute_button.setToolTip("Open Cloud Compute Offload (§4.21)")
        self.cloud_compute_button.setStyleSheet(
            qss("main_icon_btn", OBJECT_NAME="cloud_compute_button")
        )
        header_layout.addWidget(self.cloud_compute_button)

        # --- Settings button ---
        self.settings_button = QPushButton()
        if app_icon and os.path.exists(app_icon):
            settings_icon = QIcon(app_icon)
            self.settings_button.setIcon(settings_icon)
        else:
            settings_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ToolBarHorizontalExtensionButton)
            self.settings_button.setIcon(settings_icon)

        self.settings_button.setIconSize(QSize(24, 24))
        self.settings_button.setFixedSize(QSize(36, 36))
        self.settings_button.setObjectName("settings_button")
        self.settings_button.setToolTip("Open Settings")
        self.settings_button.setDefault(True)

        self.settings_button.setStyleSheet(
            qss("main_icon_btn", OBJECT_NAME="settings_button")
        )
        header_layout.addWidget(self.settings_button)

        return header_widget


__all__ = ["_HeaderBuilderMixin"]
