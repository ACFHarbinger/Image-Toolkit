"""Modern Dashboard-style Resource Usage Simulator Widget.

Visualizes estimated RAM demand, CPU worker concurrency, system memory capacity,
and swap overflow risk for parallel video extraction tasks.
"""

from __future__ import annotations

import logging
from typing import Optional

import psutil
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gui.src.theming.theme_api import color, qss

log = logging.getLogger(__name__)


class MetricCard(QFrame):
    """A KPI stat card showing a category, primary value, and subtitle."""

    def __init__(
        self,
        category: str,
        initial_value: str = "--",
        initial_subtext: str = "",
        icon: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("metric_card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setStyleSheet(qss("resource_metric_card"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        if icon:
            self.icon_label = QLabel(icon)
            self.icon_label.setStyleSheet(qss("resource_icon_label"))
            header_layout.addWidget(self.icon_label)

        self.category_label = QLabel(category.upper())
        self.category_label.setStyleSheet(qss("resource_category_label"))
        header_layout.addWidget(self.category_label)
        header_layout.addStretch(1)
        layout.addLayout(header_layout)

        self.value_label = QLabel(initial_value)
        self.value_label.setStyleSheet(qss("resource_value_default"))
        layout.addWidget(self.value_label)

        self.subtext_label = QLabel(initial_subtext)
        self.subtext_label.setStyleSheet(qss("resource_subtext"))
        self.subtext_label.setWordWrap(True)
        layout.addWidget(self.subtext_label)

    def set_data(
        self,
        value: str,
        subtext: Optional[str] = None,
        value_color: Optional[str] = None,
    ) -> None:
        self.value_label.setText(value)
        if subtext is not None:
            self.subtext_label.setText(subtext)
        tone = value_color or color("accent")
        self.value_label.setStyleSheet(
            qss("resource_value_dynamic", VALUE_COLOR=tone)
        )


class ResourceSimulatorDashboard(QFrame):
    """Dashboard widget visualizing parallel extraction resource simulation."""

    BASE_RAM_MIB = 512
    PER_WORKER_RAM_MIB = 4096
    OS_RESERVE_FRACTION = 0.12
    OS_RESERVE_MIN_GIB = 2
    LOW_SWAP_GIB = 4

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("resource_simulator_dashboard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(qss("resource_dashboard_root"))

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)

        title_lbl = QLabel("📊 Resource Allocation Simulator")
        title_lbl.setStyleSheet(qss("resource_title"))
        subtitle_lbl = QLabel("Real-time memory & swap overhead modeling for parallel extraction workers")
        subtitle_lbl.setStyleSheet(qss("resource_subtitle"))

        title_box.addWidget(title_lbl)
        title_box.addWidget(subtitle_lbl)
        header_layout.addLayout(title_box)
        header_layout.addStretch(1)

        self.status_badge = QLabel("⏸️ Queue Disabled")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet(qss("resource_status_badge_idle"))
        header_layout.addWidget(self.status_badge)
        root_layout.addLayout(header_layout)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(6)
        cards_layout.setContentsMargins(0, 0, 0, 0)

        self.card_workers = MetricCard(
            "Concurrency", "1 Process",
            f"Base {self.BASE_RAM_MIB} MiB + {self.PER_WORKER_RAM_MIB / 1024:.1f} GiB/ea", "⚙️",
        )
        self.card_est_ram = MetricCard("Est. Peak RAM", "--", "Peak, est.", "📦")
        self.card_sys_ram = MetricCard("Available RAM", "-- GiB", "Free physical RAM", "💾")
        self.card_swap = MetricCard("Swap Risk", "0.0 GiB", "Paging pressure", "🔄")

        cards_layout.addWidget(self.card_workers)
        cards_layout.addWidget(self.card_est_ram)
        cards_layout.addWidget(self.card_sys_ram)
        cards_layout.addWidget(self.card_swap)
        root_layout.addLayout(cards_layout)

        gauges_box = QFrame()
        gauges_box.setStyleSheet(qss("resource_panel_frame"))
        gauges_layout = QVBoxLayout(gauges_box)
        gauges_layout.setContentsMargins(8, 6, 8, 6)
        gauges_layout.setSpacing(6)

        ram_label_row = QHBoxLayout()
        ram_label_row.setContentsMargins(0, 0, 0, 0)
        self.ram_bar_title = QLabel("RAM Demand vs Available Memory")
        self.ram_bar_title.setStyleSheet(qss("resource_bar_title"))
        self.ram_bar_value_lbl = QLabel("0%")
        self.ram_bar_value_lbl.setStyleSheet(qss("resource_bar_value_accent"))
        ram_label_row.addWidget(self.ram_bar_title)
        ram_label_row.addStretch(1)
        ram_label_row.addWidget(self.ram_bar_value_lbl)
        gauges_layout.addLayout(ram_label_row)

        self.ram_progress_bar = QProgressBar()
        self.ram_progress_bar.setRange(0, 100)
        self.ram_progress_bar.setValue(0)
        self.ram_progress_bar.setTextVisible(False)
        self.ram_progress_bar.setFixedHeight(8)
        self._set_progress_bar_style(self.ram_progress_bar, color("success"))
        gauges_layout.addWidget(self.ram_progress_bar)

        swap_label_row = QHBoxLayout()
        swap_label_row.setContentsMargins(0, 0, 0, 0)
        self.swap_bar_title = QLabel("Swap Overhead Risk")
        self.swap_bar_title.setStyleSheet(qss("resource_bar_title"))
        self.swap_bar_value_lbl = QLabel("0.0 GiB (Clean)")
        self.swap_bar_value_lbl.setStyleSheet(qss("resource_bar_value_success"))
        swap_label_row.addWidget(self.swap_bar_title)
        swap_label_row.addStretch(1)
        swap_label_row.addWidget(self.swap_bar_value_lbl)
        gauges_layout.addLayout(swap_label_row)

        self.swap_progress_bar = QProgressBar()
        self.swap_progress_bar.setRange(0, 100)
        self.swap_progress_bar.setValue(0)
        self.swap_progress_bar.setTextVisible(False)
        self.swap_progress_bar.setFixedHeight(8)
        self._set_progress_bar_style(self.swap_progress_bar, color("success"))
        gauges_layout.addWidget(self.swap_progress_bar)

        root_layout.addWidget(gauges_box)

        summary_box = QFrame()
        summary_box.setStyleSheet(qss("resource_panel_frame"))
        summary_layout = QVBoxLayout(summary_box)
        summary_layout.setContentsMargins(8, 6, 8, 6)
        summary_layout.setSpacing(3)

        self.advisory_label = QLabel()
        self.advisory_label.setWordWrap(True)
        self.advisory_label.setStyleSheet(qss("resource_advisory"))
        summary_layout.addWidget(self.advisory_label)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet(qss("resource_subtext"))
        summary_layout.addWidget(self.summary_label)

        root_layout.addWidget(summary_box)

    def _set_progress_bar_style(self, bar: QProgressBar, chunk_color: str) -> None:
        bar.setStyleSheet(qss("resource_progress_bar", CHUNK_COLOR=chunk_color))

    def update_simulation(
        self,
        enabled: bool,
        workers: int,
        ram_available: Optional[float] = None,
        ram_total: Optional[float] = None,
        swap_free: Optional[float] = None,
        swap_total: Optional[float] = None,
        per_worker_mib: Optional[int] = None,
    ) -> None:
        """Update dashboard state based on worker count and system memory metrics."""
        gib = 1024 ** 3
        mib = 1024 ** 2
        muted = color("text")

        if not enabled:
            self.status_badge.setText("⏸️ Queue Disabled")
            self.status_badge.setStyleSheet(qss("resource_status_badge_idle"))
            self.card_workers.set_data("Disabled", "Queue execution off", muted)
            self.card_est_ram.set_data("0.0 GiB", "No parallel buffer", muted)
            try:
                mem = psutil.virtual_memory()
                self.card_sys_ram.set_data(
                    f"{mem.available / gib:.1f} GiB",
                    f"Total: {mem.total / gib:.1f} GiB",
                    muted,
                )
            except Exception:
                self.card_sys_ram.set_data("-- GiB", "System RAM", muted)
            self.card_swap.set_data("0.0 GiB", "No risk", muted)

            self.ram_progress_bar.setValue(0)
            self.ram_bar_value_lbl.setText("0%")
            self.swap_progress_bar.setValue(0)
            self.swap_bar_value_lbl.setText("0% (Clean)")
            self.advisory_label.setText(
                "💡 Extraction queue is disabled. Enable the checkbox above to simulate memory allocation across parallel workers."
            )
            self.summary_label.setText(
                "Enable Extraction Queue to configure parallel processors and view estimates."
            )
            return

        try:
            memory = psutil.virtual_memory()
            avail_bytes = ram_available if ram_available is not None else memory.available
            total_bytes = ram_total if ram_total is not None else memory.total
        except Exception:
            avail_bytes = 8 * gib
            total_bytes = 16 * gib

        try:
            swap = psutil.swap_memory()
            free_swap_bytes = swap_free if swap_free is not None else swap.free
            total_swap_bytes = swap_total if swap_total is not None else swap.total
        except Exception:
            free_swap_bytes = 4 * gib
            total_swap_bytes = 8 * gib

        per_worker = (per_worker_mib or self.PER_WORKER_RAM_MIB) * mib
        estimated_ram = (self.BASE_RAM_MIB * mib) + workers * per_worker

        os_reserve = max(self.OS_RESERVE_MIN_GIB * gib, int(total_bytes * self.OS_RESERVE_FRACTION))
        usable_bytes = max(avail_bytes - os_reserve, 1)

        low_swap = total_swap_bytes < self.LOW_SWAP_GIB * gib
        potential_swap = max(estimated_ram - usable_bytes, 0)
        freeze_risk = low_swap and estimated_ram > usable_bytes * 0.85

        ram_demand_pct = int(min(100, round((estimated_ram / usable_bytes) * 100)))
        if total_swap_bytes > 0 and potential_swap > 0:
            swap_demand_pct = int(min(100, round((potential_swap / total_swap_bytes) * 100)))
        else:
            swap_demand_pct = 0

        accent = color("accent")
        danger = color("danger")
        success = color("success")
        warning = color("accent_hover")

        worker_str = f"{workers} Process" if workers == 1 else f"{workers} Processes"
        self.card_workers.set_data(
            worker_str,
            f"~{self.BASE_RAM_MIB} MiB base + {per_worker / gib:.1f} GiB/ea",
            accent,
        )
        self.card_est_ram.set_data(
            f"~{estimated_ram / gib:.1f} GiB",
            "Peak, est.",
            accent if (potential_swap == 0 and not freeze_risk) else danger,
        )
        self.card_sys_ram.set_data(
            f"{usable_bytes / gib:.1f} GiB",
            f"Free {avail_bytes / gib:.1f} · reserve {os_reserve / gib:.1f} · total {total_bytes / gib:.1f}",
            accent,
        )

        if potential_swap > 0 or freeze_risk:
            self.card_swap.set_data(
                f"~{potential_swap / gib:.1f} GiB",
                f"Swap free: {free_swap_bytes / gib:.1f} GiB",
                danger,
            )
            self.status_badge.setText("🧊 Freeze Risk" if freeze_risk else "🔴 Swap Warning")
            self.status_badge.setStyleSheet(qss("resource_status_badge_danger"))
            self._set_progress_bar_style(self.ram_progress_bar, danger)
            self._set_progress_bar_style(self.swap_progress_bar, danger)
            self.ram_bar_value_lbl.setStyleSheet(qss("resource_bar_value_danger"))
            self.swap_bar_value_lbl.setStyleSheet(qss("resource_bar_value_danger"))
            self.swap_bar_value_lbl.setText(f"~{potential_swap / gib:.1f} GiB Paging")
            if freeze_risk:
                self.advisory_label.setText(
                    f"🧊 Freeze risk: estimated peak ~{estimated_ram / gib:.1f} GiB is near/over the "
                    f"~{usable_bytes / gib:.1f} GiB usable and this system has only "
                    f"{total_swap_bytes / gib:.1f} GiB swap — RAM exhaustion here tends to hard-hang "
                    f"the desktop (no clean OOM-kill), not just slow extraction. Reduce workers or add swap/zram."
                )
            else:
                self.advisory_label.setText(
                    f"⚠️ High memory pressure: estimated peak ~{estimated_ram / gib:.1f} GiB exceeds the "
                    f"~{usable_bytes / gib:.1f} GiB usable (after a {os_reserve / gib:.1f} GiB OS/app reserve) "
                    f"by ~{potential_swap / gib:.1f} GiB. Disk paging will slow extraction — reduce worker count."
                )
        elif ram_demand_pct >= 75:
            self.card_swap.set_data(
                "0.0 GiB",
                f"Swap free: {free_swap_bytes / gib:.1f} GiB",
                warning,
            )
            self.status_badge.setText("🟡 Moderate Load")
            self.status_badge.setStyleSheet(qss("resource_status_badge_warning"))
            self._set_progress_bar_style(self.ram_progress_bar, warning)
            self._set_progress_bar_style(self.swap_progress_bar, success)
            self.ram_bar_value_lbl.setStyleSheet(qss("resource_bar_value_warning"))
            self.swap_bar_value_lbl.setStyleSheet(qss("resource_bar_value_success"))
            self.swap_bar_value_lbl.setText("0.0 GiB (Clean)")
            self.advisory_label.setText(
                f"⚡ Elevated footprint (~{ram_demand_pct}% of the {usable_bytes / gib:.1f} GiB usable). "
                f"Should fit in RAM now, but little headroom — a point-in-time estimate; real usage varies "
                f"with video resolution/codec and drops as you launch other apps."
            )
        else:
            self.card_swap.set_data(
                "0.0 GiB",
                f"Swap free: {free_swap_bytes / gib:.1f} GiB",
                success,
            )
            self.status_badge.setText("🟢 Optimal Headroom")
            self.status_badge.setStyleSheet(qss("resource_status_badge_ok"))
            self._set_progress_bar_style(self.ram_progress_bar, success)
            self._set_progress_bar_style(self.swap_progress_bar, success)
            self.ram_bar_value_lbl.setStyleSheet(qss("resource_bar_value_success"))
            self.swap_bar_value_lbl.setStyleSheet(qss("resource_bar_value_success"))
            self.swap_bar_value_lbl.setText("0.0 GiB (Clean)")
            self.advisory_label.setText(
                f"✓ Comfortable: ~{ram_demand_pct}% of the {usable_bytes / gib:.1f} GiB usable "
                f"(after a {os_reserve / gib:.1f} GiB OS/app reserve). Point-in-time estimate — "
                f"real per-worker RAM varies with video resolution/codec."
            )

        self.ram_progress_bar.setValue(ram_demand_pct)
        self.ram_bar_value_lbl.setText(f"{ram_demand_pct}% ({estimated_ram / gib:.1f} GiB)")

        self.swap_progress_bar.setValue(swap_demand_pct)

        self.summary_label.setText(
            f"~{workers} × {per_worker / gib:.1f} GiB + {self.BASE_RAM_MIB} MiB ≈ "
            f"{estimated_ram / gib:.1f} GiB peak RAM vs {usable_bytes / gib:.1f} GiB usable RAM "
            f"({avail_bytes / gib:.1f} free − {os_reserve / gib:.1f} reserve). "
            f"Overflow ~{potential_swap / gib:.1f} GiB; swap total {total_swap_bytes / gib:.1f} GiB."
        )


__all__ = ["MetricCard", "ResourceSimulatorDashboard"]
