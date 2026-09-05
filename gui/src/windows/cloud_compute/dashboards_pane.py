"""Dashboards pane for Cloud Compute Offload window (§4.21, #488, #490).

Provides telemetry aggregation, compute time, egress metrics, cost estimates,
and integration slots for charting and telemetry dataviz components.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.src.web.cloud.compute.usage import (
    UsageRow,
    UsageRowSource,
    aggregate_usage_rows,
    format_bytes,
    format_duration,
    format_usd,
)
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

from gui.src.windows.cloud_compute.usage_charts import (
    _BarChart,
    _GroupedBarChart,
    bars_from_duration,
    groups_from_summary,
)


class DashboardsPane(QWidget):
    """Analytics and resource-usage dashboard for cloud compute tasks."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._source = UsageRowSource()
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
        self.chart_container.setObjectName("usage_chart_container")
        self.chart_container.setStyleSheet(
            "QFrame#usage_chart_container { border: 1px solid #30363d; border-radius: 8px; min-height: 180px; }"
        )
        chart_inner_layout = QHBoxLayout(self.chart_container)
        chart_inner_layout.setContentsMargins(4, 4, 4, 4)
        chart_inner_layout.setSpacing(8)
        self.chart_duration = _BarChart("Per-job wall time (s)")
        self.chart_providers = _GroupedBarChart()
        chart_inner_layout.addWidget(self.chart_duration, 1)
        chart_inner_layout.addWidget(self.chart_providers, 1)

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
        parsed = UsageRow.from_mapping(row_data)
        self._source.add(parsed)
        self._usage_rows.append(row_data)
        row = self.table_usage.rowCount()
        self.table_usage.insertRow(row)
        duration = (
            str(row_data.get("duration", ""))
            if parsed.status == "in_flight"
            else format_duration(parsed.duration_seconds)
        )
        egress = str(row_data.get("egress", "")) or format_bytes(parsed.egress_bytes)
        cost = str(row_data.get("cost", "")) or format_usd(parsed.cost_usd)
        self.table_usage.setItem(row, 0, QTableWidgetItem(parsed.timestamp))
        self.table_usage.setItem(row, 1, QTableWidgetItem(parsed.job_id))
        self.table_usage.setItem(row, 2, QTableWidgetItem(parsed.provider.upper()))
        self.table_usage.setItem(row, 3, QTableWidgetItem(parsed.task))
        self.table_usage.setItem(row, 4, QTableWidgetItem(duration))
        self.table_usage.setItem(row, 5, QTableWidgetItem(egress))
        self.table_usage.setItem(row, 6, QTableWidgetItem(cost))
        self._update_kpi_aggregations()

    def _update_kpi_aggregations(self) -> None:
        summary = aggregate_usage_rows(self._source.load_rows())
        pairs = (
            (self.card_total_jobs, "kpi_val_total_jobs", summary.total_jobs_label),
            (self.card_total_time, "kpi_val_compute_time", summary.compute_time_label),
            (self.card_egress, "kpi_val_data_transferred", summary.egress_label),
            (self.card_cost, "kpi_val_estimated_spend", summary.cost_label),
            (self.card_success_rate, "kpi_val_success_rate", summary.success_rate_label),
        )
        for card, name, text in pairs:
            lbl = card.findChild(QLabel, name)
            if lbl:
                lbl.setText(text)
        self.chart_duration.set_bars(bars_from_duration(summary.series))
        self.chart_providers.set_groups(groups_from_summary(summary))

    def _refresh_metrics(self) -> None:
        self._update_kpi_aggregations()
