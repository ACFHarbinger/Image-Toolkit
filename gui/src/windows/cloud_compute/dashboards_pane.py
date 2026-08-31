"""Dashboards pane for Cloud Compute Offload window (§4.21, #488, #490).

Provides telemetry aggregation, compute time, egress metrics, cost estimates,
and integration slots for charting and telemetry dataviz components.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class DashboardsPane(QWidget):
    """Analytics and resource-usage dashboard for cloud compute tasks."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._usage_rows: List[Dict[str, Any]] = []

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

        # ── KPI Tiles Row ────────────────────────────────────────────────────
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(10)

        self.card_total_jobs = self._create_kpi_card("Total Jobs", "0", "#79c0ff")
        self.card_total_time = self._create_kpi_card("Compute Time", "0s", "#56d364")
        self.card_egress = self._create_kpi_card("Data Transferred", "0 MB", "#f0883e")
        self.card_cost = self._create_kpi_card("Estimated Spend", "$0.00", "#d2a8ff")
        self.card_success_rate = self._create_kpi_card("Success Rate", "100%", "#56d364")

        kpi_grid.addWidget(self.card_total_jobs, 0, 0)
        kpi_grid.addWidget(self.card_total_time, 0, 1)
        kpi_grid.addWidget(self.card_egress, 0, 2)
        kpi_grid.addWidget(self.card_cost, 0, 3)
        kpi_grid.addWidget(self.card_success_rate, 0, 4)

        layout.addLayout(kpi_grid)

        # ── Visual Telemetry & Chart Slot ────────────────────────────────────
        group_charts = QGroupBox("Resource Trends & Performance")
        group_charts.setStyleSheet("QGroupBox { font-weight: bold; color: #f0f6fc; }")
        chart_layout = QVBoxLayout(group_charts)
        chart_layout.setContentsMargins(14, 14, 14, 14)

        self.chart_container = QFrame()
        self.chart_container.setStyleSheet(
            "background-color: #0d1117; border: 1px dashed #30363d; border-radius: 8px; min-height: 160px;"
        )
        chart_inner_layout = QVBoxLayout(self.chart_container)
        chart_inner_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_chart_placeholder = QLabel("📊 Telemetry & Resource Visualization (#490)\n(Live vCPU, RAM, and egress trend charts)")
        self.lbl_chart_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_chart_placeholder.setStyleSheet("color: #8b949e; font-size: 10pt; font-style: italic;")
        chart_inner_layout.addWidget(self.lbl_chart_placeholder)

        chart_layout.addWidget(self.chart_container)
        layout.addWidget(group_charts)

        # ── Historical Usage Rows Table ──────────────────────────────────────
        group_table = QGroupBox("Cloud Usage Log")
        group_table.setStyleSheet("QGroupBox { font-weight: bold; color: #f0f6fc; }")
        table_layout = QVBoxLayout(group_table)
        table_layout.setContentsMargins(12, 12, 12, 12)

        self.table_usage = QTableWidget(0, 7)
        self.table_usage.setHorizontalHeaderLabels([
            "Timestamp", "Job ID", "Provider", "Task", "Duration", "Egress", "Cost Est."
        ])
        self.table_usage.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_usage.setStyleSheet(
            "QTableWidget { background-color: #0d1117; border: 1px solid #30363d; "
            "color: #c9d1d9; gridline-color: #21262d; }"
            "QHeaderView::section { background-color: #161b22; color: #8b949e; font-weight: bold; padding: 4px; }"
        )
        self.table_usage.setMinimumHeight(180)
        table_layout.addWidget(self.table_usage)

        # Refresh / Clear actions
        tbl_btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh Telemetry")
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #21262d; color: #c9d1d9; border: 1px solid #30363d; "
            "border-radius: 4px; padding: 5px 12px; font-size: 8.5pt; }"
            "QPushButton:hover { background-color: #30363d; color: #f0f6fc; }"
        )
        self.btn_refresh.clicked.connect(self._refresh_metrics)
        tbl_btn_layout.addWidget(self.btn_refresh)
        tbl_btn_layout.addStretch(1)
        table_layout.addLayout(tbl_btn_layout)

        layout.addWidget(group_table)

        scroll_area.setWidget(container)
        main_layout.addWidget(scroll_area)

    def _create_kpi_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 10px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(4)

        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet("color: #8b949e; font-size: 7.5pt; font-weight: bold; letter-spacing: 0.5px;")
        card_layout.addWidget(lbl_title)

        lbl_val = QLabel(value)
        lbl_val.setObjectName(f"kpi_val_{title.lower().replace(' ', '_')}")
        lbl_val.setStyleSheet(f"color: {color}; font-size: 14pt; font-weight: bold;")
        card_layout.addWidget(lbl_val)

        return card

    def add_usage_row(self, row_data: Dict[str, Any]) -> None:
        """Add a usage record row from cloud job completion."""
        self._usage_rows.append(row_data)
        row = self.table_usage.rowCount()
        self.table_usage.insertRow(row)
        self.table_usage.setItem(row, 0, QTableWidgetItem(str(row_data.get("timestamp", ""))))
        self.table_usage.setItem(row, 1, QTableWidgetItem(str(row_data.get("job_id", ""))))
        self.table_usage.setItem(row, 2, QTableWidgetItem(str(row_data.get("provider", "")).upper()))
        self.table_usage.setItem(row, 3, QTableWidgetItem(str(row_data.get("task", ""))))
        self.table_usage.setItem(row, 4, QTableWidgetItem(str(row_data.get("duration", ""))))
        self.table_usage.setItem(row, 5, QTableWidgetItem(str(row_data.get("egress", ""))))
        self.table_usage.setItem(row, 6, QTableWidgetItem(str(row_data.get("cost", ""))))
        self._update_kpi_aggregations()

    def _update_kpi_aggregations(self) -> None:
        total_jobs = len(self._usage_rows)
        lbl_jobs = self.card_total_jobs.findChild(QLabel, "kpi_val_total_jobs")
        if lbl_jobs:
            lbl_jobs.setText(str(total_jobs))

    def _refresh_metrics(self) -> None:
        self._update_kpi_aggregations()
