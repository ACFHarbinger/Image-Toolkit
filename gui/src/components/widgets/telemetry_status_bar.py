"""Rich Telemetry Status Bar component (§2.39)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStatusBar, QWidget

from gui.src.modules.events import EventHub, EventSubscription, TelemetryUpdatedFact


class TelemetryStatusBar(QStatusBar):
    """Status bar equipped with live DB, GPU/VRAM, background queue, and layout status chips."""

    layout_toggle_requested = Signal()
    theme_dialog_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        event_hub: Optional[EventHub] = None,
    ) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.setMaximumHeight(26)
        self._event_hub: Optional[EventHub] = None
        self._subscriptions: list[EventSubscription] = []
        self._build_ui()

        if event_hub is not None:
            self.bind_event_hub(event_hub)

        # Telemetry update timer (sampled every 3 seconds)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sample_telemetry)
        self._timer.start(3000)
        self._sample_telemetry()

    def bind_event_hub(self, event_hub: EventHub) -> None:
        """Bind status bar to EventHub for typed telemetry fact subscriptions."""
        self._event_hub = event_hub
        for sub in self._subscriptions:
            sub.disconnect()
        self._subscriptions.clear()

        self._subscriptions.append(
            event_hub.subscribe(TelemetryUpdatedFact, self._on_telemetry_fact, owner=self)
        )

    def _on_telemetry_fact(self, fact: TelemetryUpdatedFact) -> None:
        if fact.db_connected is not None:
            self.set_db_status(fact.db_connected, fact.db_latency_ms)
        if fact.task_count is not None:
            self.set_task_count(fact.task_count)
        if fact.vram_allocated_gb is not None and fact.vram_total_gb is not None:
            self.gpu_chip.setText(f"⚡ VRAM: {fact.vram_allocated_gb:.1f}/{fact.vram_total_gb:.1f} GB")
        if fact.status_message is not None:
            self.set_status_message(fact.status_message)

    def _build_ui(self) -> None:
        # Left status text area
        self._status_label = QLabel("Ready // 待機中")
        self._status_label.setStyleSheet("color: #aaaaaa; padding-left: 6px; font-size: 8.5pt;")
        self.addWidget(self._status_label, 1)

        # Right Telemetry Chips
        chip_container = QWidget()
        chip_layout = QHBoxLayout(chip_container)
        chip_layout.setContentsMargins(0, 0, 6, 0)
        chip_layout.setSpacing(6)

        # 1. Database connection chip
        self.db_chip = QLabel("🟢 DB: Ready")
        self.db_chip.setStyleSheet("background: rgba(85, 197, 122, 0.15); color: #55c57a; border: 1px solid rgba(85, 197, 122, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")
        self.db_chip.setToolTip("PostgreSQL + pgvector connection status")
        chip_layout.addWidget(self.db_chip)

        # 2. GPU / VRAM usage chip
        self.gpu_chip = QLabel("⚡ VRAM: --")
        self.gpu_chip.setStyleSheet("background: rgba(0, 240, 255, 0.12); color: #00f0ff; border: 1px solid rgba(0, 240, 255, 0.25); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")
        self.gpu_chip.setToolTip("GPU Compute & VRAM telemetry")
        chip_layout.addWidget(self.gpu_chip)

        # 3. Worker task status
        self.task_chip = QLabel("🔄 Tasks: 0")
        self.task_chip.setStyleSheet("background: rgba(192, 132, 252, 0.12); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.25); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")
        self.task_chip.setToolTip("Active background tasks & workers")
        chip_layout.addWidget(self.task_chip)

        # 4. Layout switcher button chip
        self.layout_btn = QPushButton("☰ Nav")
        self.layout_btn.setStyleSheet("QPushButton { background: rgba(255, 255, 255, 0.08); color: #cccccc; border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 4px; padding: 2px 8px; font-size: 8pt; } QPushButton:hover { background: rgba(255, 255, 255, 0.15); }")
        self.layout_btn.setToolTip("Toggle Navigation Mode (Rail vs. Top Bar, Ctrl+Shift+L)")
        self.layout_btn.clicked.connect(self.layout_toggle_requested)
        chip_layout.addWidget(self.layout_btn)

        self.addPermanentWidget(chip_container)

    def set_status_message(self, message: str, timeout_ms: int = 4000) -> None:
        self._status_label.setText(message)
        if timeout_ms > 0:
            QTimer.singleShot(timeout_ms, lambda: self._status_label.setText("Ready // 待機中"))

    def set_db_status(self, connected: bool, latency_ms: Optional[float] = None) -> None:
        if connected:
            text = f"🟢 DB: {latency_ms:.0f}ms" if latency_ms is not None else "🟢 DB: Ready"
            self.db_chip.setText(text)
            self.db_chip.setStyleSheet("background: rgba(85, 197, 122, 0.15); color: #55c57a; border: 1px solid rgba(85, 197, 122, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")
        else:
            self.db_chip.setText("🔴 DB: Disconnected")
            self.db_chip.setStyleSheet("background: rgba(248, 113, 113, 0.15); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")

    def set_task_count(self, count: int) -> None:
        if count > 0:
            self.task_chip.setText(f"🔄 Tasks: {count}")
            self.task_chip.setStyleSheet("background: rgba(251, 146, 60, 0.15); color: #fb923c; border: 1px solid rgba(251, 146, 60, 0.3); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")
        else:
            self.task_chip.setText("🔄 Tasks: 0")
            self.task_chip.setStyleSheet("background: rgba(192, 132, 252, 0.12); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.25); border-radius: 4px; padding: 2px 6px; font-size: 8pt;")

    def _sample_telemetry(self) -> None:
        try:
            import torch
            if torch.cuda.is_available():
                alloc = torch.cuda.memory_allocated() / (1024 ** 3)
                total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                self.gpu_chip.setText(f"⚡ VRAM: {alloc:.1f}/{total:.1f} GB")
            else:
                self.gpu_chip.setText("⚡ CPU Mode")
        except Exception:
            self.gpu_chip.setText("⚡ CPU Mode")


__all__ = ["TelemetryStatusBar"]
