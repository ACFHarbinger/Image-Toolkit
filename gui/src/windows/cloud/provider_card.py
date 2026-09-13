"""Descriptor card widget for Cloud Compute Offload providers (§4.21, #488).

Presents provider capabilities, hardware shapes, memory tiers, cold-start
latencies, cost estimates, regions, and deployment configuration references.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.theme_api import color, qss


@dataclass
class ProviderDescriptor:
    """Specification data model for a cloud compute offload provider."""

    provider_id: str
    name: str
    badge_text: str
    badge_color: str
    description: str
    target_service: str
    cpu_shapes: str
    memory_tiers: str
    gpu_options: str
    cost_estimate: str
    cold_start: str
    regions: List[str] = field(default_factory=list)
    config_file: str = ""
    is_poc_target: bool = False


class ProviderDescriptorCard(QFrame):
    """Clickable descriptor card presenting a cloud compute provider's attributes."""

    selected = Signal(str)  # Emits provider_id on selection

    def __init__(
        self,
        descriptor: ProviderDescriptor,
        is_selected: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.descriptor = descriptor
        self._is_selected = is_selected

        self.setObjectName(f"provider_card_{descriptor.provider_id}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._build_ui()
        self._update_selection_style()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # ── Header: Title + Badge + Select Button ────────────────────────────
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.title_label = QLabel(self.descriptor.name)
        self.title_label.setStyleSheet(qss("cloud_window_title"))
        header_layout.addWidget(self.title_label)

        badge_rgb = self._hex_to_rgb(self.descriptor.badge_color)
        self.badge_label = QLabel(f" {self.descriptor.badge_text} ")
        self.badge_label.setStyleSheet(
            qss(
                "cloud_provider_badge",
                BADGE_COLOR=self.descriptor.badge_color,
                BADGE_R=badge_rgb[0],
                BADGE_G=badge_rgb[1],
                BADGE_B=badge_rgb[2],
            )
        )
        header_layout.addWidget(self.badge_label)
        header_layout.addStretch(1)

        self.btn_select = QPushButton("Active Target" if self._is_selected else "Select Provider")
        self.btn_select.setCheckable(True)
        self.btn_select.setChecked(self._is_selected)
        self.btn_select.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_select.clicked.connect(self._on_select_clicked)
        header_layout.addWidget(self.btn_select)

        layout.addLayout(header_layout)

        # ── Description ──────────────────────────────────────────────────────
        self.desc_label = QLabel(self.descriptor.description)
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet(qss("cloud_window_subtitle"))
        layout.addWidget(self.desc_label)

        # ── Specs KPI Grid ───────────────────────────────────────────────────
        specs_container = QFrame()
        specs_container.setStyleSheet(qss("cloud_specs_panel"))
        specs_layout = QGridLayout(specs_container)
        specs_layout.setContentsMargins(12, 10, 12, 10)
        specs_layout.setHorizontalSpacing(16)
        specs_layout.setVerticalSpacing(8)

        def make_kpi(col: int, row: int, label: str, value: str, value_color: str) -> None:
            lbl_title = QLabel(label.upper())
            lbl_title.setStyleSheet(qss("resource_category_label"))
            lbl_val = QLabel(value)
            lbl_val.setStyleSheet(qss("resource_value_dynamic", VALUE_COLOR=value_color))
            specs_layout.addWidget(lbl_title, row * 2, col)
            specs_layout.addWidget(lbl_val, row * 2 + 1, col)

        make_kpi(0, 0, "Compute Shape", self.descriptor.cpu_shapes, color("accent_hover"))
        make_kpi(1, 0, "Memory Tier", self.descriptor.memory_tiers, color("success"))
        make_kpi(2, 0, "GPU Acceleration", self.descriptor.gpu_options, color("accent"))
        make_kpi(0, 1, "Cold Start Latency", self.descriptor.cold_start, color("accent_hover"))
        make_kpi(1, 1, "Estimated Cost", self.descriptor.cost_estimate, color("success"))
        make_kpi(2, 1, "Target Service", self.descriptor.target_service, color("muted_text"))

        layout.addWidget(specs_container)

        # ── Footer: Region Selector + Config Reference ───────────────────────
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        lbl_region = QLabel("Target Region:")
        lbl_region.setStyleSheet(qss("cloud_window_subtitle"))
        footer_layout.addWidget(lbl_region)

        self.region_combo = QComboBox()
        self.region_combo.addItems(self.descriptor.regions)
        self.region_combo.setStyleSheet(qss("cloud_region_combo"))
        footer_layout.addWidget(self.region_combo)

        footer_layout.addStretch(1)

        if self.descriptor.config_file:
            lbl_cfg = QLabel(f"📄 Config: <code>{self.descriptor.config_file}</code>")
            lbl_cfg.setTextFormat(Qt.TextFormat.RichText)
            lbl_cfg.setStyleSheet(qss("resource_category_label"))
            footer_layout.addWidget(lbl_cfg)

        layout.addLayout(footer_layout)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self._on_select_clicked()

    def _on_select_clicked(self) -> None:
        self.set_selected(True)
        self.selected.emit(self.descriptor.provider_id)

    def set_selected(self, selected: bool) -> None:
        self._is_selected = selected
        self.btn_select.setChecked(selected)
        self.btn_select.setText("Active Target" if selected else "Select Provider")
        self._update_selection_style()

    def is_selected(self) -> bool:
        return self._is_selected

    def selected_region(self) -> str:
        return self.region_combo.currentText()

    def _update_selection_style(self) -> None:
        object_name = self.objectName()
        if self._is_selected:
            self.setStyleSheet(qss("cloud_provider_card_selected", OBJECT_NAME=object_name))
            self.btn_select.setStyleSheet(qss("cloud_provider_btn_active"))
        else:
            self.setStyleSheet(qss("cloud_provider_card_default", OBJECT_NAME=object_name))
            self.btn_select.setStyleSheet(qss("cloud_provider_btn_select"))

    @staticmethod
    def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
        h = hex_str.lstrip("#")
        if len(h) == 6:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return 88, 166, 255
