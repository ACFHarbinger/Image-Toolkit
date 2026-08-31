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
        self.title_label.setStyleSheet("font-size: 13pt; font-weight: bold; color: #f0f6fc;")
        header_layout.addWidget(self.title_label)

        self.badge_label = QLabel(f" {self.descriptor.badge_text} ")
        self.badge_label.setStyleSheet(
            f"background-color: rgba({self._hex_to_rgb(self.descriptor.badge_color)}, 0.20);"
            f"color: {self.descriptor.badge_color}; border: 1px solid {self.descriptor.badge_color};"
            "border-radius: 4px; font-size: 8.5pt; font-weight: bold; padding: 2px 6px;"
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
        self.desc_label.setStyleSheet("color: #8b949e; font-size: 9.5pt; line-height: 1.3;")
        layout.addWidget(self.desc_label)

        # ── Specs KPI Grid ───────────────────────────────────────────────────
        specs_container = QFrame()
        specs_container.setStyleSheet(
            "background-color: #0d1117; border: 1px solid #30363d; border-radius: 6px;"
        )
        specs_layout = QGridLayout(specs_container)
        specs_layout.setContentsMargins(12, 10, 12, 10)
        specs_layout.setHorizontalSpacing(16)
        specs_layout.setVerticalSpacing(8)

        def make_kpi(col: int, row: int, label: str, value: str, color: str = "#c9d1d9"):
            lbl_title = QLabel(label.upper())
            lbl_title.setStyleSheet("color: #6e7681; font-size: 7.5pt; font-weight: bold; letter-spacing: 0.5px;")
            lbl_val = QLabel(value)
            lbl_val.setStyleSheet(f"color: {color}; font-size: 9pt; font-weight: 600;")
            specs_layout.addWidget(lbl_title, row * 2, col)
            specs_layout.addWidget(lbl_val, row * 2 + 1, col)

        make_kpi(0, 0, "Compute Shape", self.descriptor.cpu_shapes, "#79c0ff")
        make_kpi(1, 0, "Memory Tier", self.descriptor.memory_tiers, "#56d364")
        make_kpi(2, 0, "GPU Acceleration", self.descriptor.gpu_options, "#d2a8ff")

        make_kpi(0, 1, "Cold Start Latency", self.descriptor.cold_start, "#f0883e")
        make_kpi(1, 1, "Estimated Cost", self.descriptor.cost_estimate, "#56d364")
        make_kpi(2, 1, "Target Service", self.descriptor.target_service, "#8b949e")

        layout.addWidget(specs_container)

        # ── Footer: Region Selector + Config Reference ───────────────────────
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        lbl_region = QLabel("Target Region:")
        lbl_region.setStyleSheet("color: #8b949e; font-size: 8.5pt; font-weight: bold;")
        footer_layout.addWidget(lbl_region)

        self.region_combo = QComboBox()
        self.region_combo.addItems(self.descriptor.regions)
        self.region_combo.setStyleSheet(
            "QComboBox { background-color: #21262d; border: 1px solid #30363d; "
            "color: #c9d1d9; border-radius: 4px; padding: 3px 8px; font-size: 8.5pt; min-width: 140px; }"
        )
        footer_layout.addWidget(self.region_combo)

        footer_layout.addStretch(1)

        if self.descriptor.config_file:
            lbl_cfg = QLabel(f"📄 Config: <code>{self.descriptor.config_file}</code>")
            lbl_cfg.setTextFormat(Qt.TextFormat.RichText)
            lbl_cfg.setStyleSheet("color: #6e7681; font-size: 8pt;")
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
        if self._is_selected:
            self.setStyleSheet(
                "QFrame#" + self.objectName() + " {"
                "  background-color: #161b22; border: 2px solid #58a6ff; border-radius: 8px;"
                "}"
            )
            self.btn_select.setStyleSheet(
                "QPushButton { background-color: #1f6feb; color: white; border: 1px solid #388bfd;"
                "border-radius: 4px; padding: 5px 12px; font-weight: bold; font-size: 9pt; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#" + self.objectName() + " {"
                "  background-color: #161b22; border: 1px solid #30363d; border-radius: 8px;"
                "}"
                "QFrame#" + self.objectName() + ":hover {"
                "  border: 1px solid #58a6ff; background-color: #1c2128;"
                "}"
            )
            self.btn_select.setStyleSheet(
                "QPushButton { background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d;"
                "border-radius: 4px; padding: 5px 12px; font-size: 9pt; }"
                "QPushButton:hover { background-color: #30363d; color: #f0f6fc; border-color: #8b949e; }"
            )

    @staticmethod
    def _hex_to_rgb(hex_str: str) -> str:
        h = hex_str.lstrip("#")
        if len(h) == 6:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"{r}, {g}, {b}"
        return "88, 166, 255"
