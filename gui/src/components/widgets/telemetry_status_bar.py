"""Rich Telemetry Status Bar component (§2.39, #540)."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QStatusBar, QWidget

from gui.src.modules.context import ModuleContext
from gui.src.modules.events import EventHub, EventSubscription, TelemetryUpdatedFact
from gui.src.modules.library_service import LIBRARY_DATABASE_SERVICE
from gui.src.qt_event_bridge import QtEventBridge
from gui.src.theming.theme_api import qss


def create_telemetry_bridge(
    event_hub: EventHub,
    parent: Optional[QObject] = None,
) -> QtEventBridge:
    """Create a QtEventBridge that forwards telemetry facts from worker threads to EventHub on GUI thread."""
    return QtEventBridge(event_hub.publish, parent=parent)


class TelemetryStatusBar(QStatusBar):
    """Status bar equipped with live DB, GPU/VRAM, background queue, and layout status chips."""

    layout_toggle_requested = Signal()
    theme_dialog_requested = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        event_hub: Optional[EventHub] = None,
        context: Optional[ModuleContext] = None,
        *,
        coalesce_interval_ms: int = 0,
        sample_interval_ms: int = 3000,
    ) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.setMaximumHeight(26)
        self._event_hub: Optional[EventHub] = None
        self._context: Optional[ModuleContext] = context
        self._subscriptions: list[EventSubscription] = []
        self._coalesce_interval_ms = coalesce_interval_ms
        self._pending_fact_values: dict[str, Any] = {}

        self._coalesce_timer = QTimer(self)
        self._coalesce_timer.setSingleShot(True)
        self._coalesce_timer.timeout.connect(self.flush_telemetry)

        self._status_reset_timer = QTimer(self)
        self._status_reset_timer.setSingleShot(True)
        self._status_reset_timer.timeout.connect(self._reset_status_message)

        self._build_ui()

        hub = event_hub or (context.event_hub if context is not None else None)
        if hub is not None:
            self.bind_event_hub(hub)

        self._disposed = False

        # Telemetry update timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._sample_telemetry)
        if sample_interval_ms > 0:
            self._timer.start(sample_interval_ms)
            # Defer the first sample off the constructor path: _sample_telemetry()
            # does `import torch` + torch.cuda.is_available(), which measures
            # ~0.9s cold (import + CUDA context init) -- calling it synchronously
            # here would block MainWindow.__init__ by that much for every user
            # with the experimental runtime shell enabled. Same "don't do heavy
            # work during construction" rule the #536/#538 anti-eager-mounting
            # contract enforces for module factories.
            #
            # A bare QTimer.singleShot(0, ...) isn't retained or cancelable
            # (the same #536 dispose-race lesson): retain a real timer so
            # dispose() can stop it, plus guard the callback itself in case
            # it's already in the event queue when disposal runs.
            self._initial_sample_timer = QTimer(self)
            self._initial_sample_timer.setSingleShot(True)
            self._initial_sample_timer.timeout.connect(self._sample_telemetry)
            self._initial_sample_timer.start(0)

    def bind_event_hub(self, event_hub: EventHub) -> None:
        """Bind status bar to EventHub for typed telemetry fact subscriptions."""
        self._event_hub = event_hub
        for sub in self._subscriptions:
            sub.disconnect()
        self._subscriptions.clear()

        self._subscriptions.append(
            event_hub.subscribe(TelemetryUpdatedFact, self._on_telemetry_fact, owner=self)
        )

    def create_bridge(self) -> Optional[QtEventBridge]:
        """Return a thread-safe QtEventBridge to forward TelemetryUpdatedFact from background workers."""
        if self._event_hub is None:
            return None
        return create_telemetry_bridge(self._event_hub, parent=self)

    def _on_telemetry_fact(self, fact: TelemetryUpdatedFact) -> None:
        if self._coalesce_interval_ms <= 0:
            self._apply_fact_fields(
                db_connected=fact.db_connected,
                db_latency_ms=fact.db_latency_ms,
                task_count=fact.task_count,
                vram_allocated_gb=fact.vram_allocated_gb,
                vram_total_gb=fact.vram_total_gb,
                status_message=fact.status_message,
            )
            return

        # Coalesce: buffer non-None values
        if fact.db_connected is not None:
            self._pending_fact_values['db_connected'] = fact.db_connected
        if fact.db_latency_ms is not None:
            self._pending_fact_values['db_latency_ms'] = fact.db_latency_ms
        if fact.task_count is not None:
            self._pending_fact_values['task_count'] = fact.task_count
        if fact.vram_allocated_gb is not None:
            self._pending_fact_values['vram_allocated_gb'] = fact.vram_allocated_gb
        if fact.vram_total_gb is not None:
            self._pending_fact_values['vram_total_gb'] = fact.vram_total_gb
        if fact.status_message is not None:
            self._pending_fact_values['status_message'] = fact.status_message

        if not self._coalesce_timer.isActive():
            self._coalesce_timer.start(self._coalesce_interval_ms)

    def flush_telemetry(self) -> None:
        """Flush any coalesced telemetry updates immediately."""
        self._coalesce_timer.stop()
        if not self._pending_fact_values:
            return
        values = dict(self._pending_fact_values)
        self._pending_fact_values.clear()
        self._apply_fact_fields(**values)

    def _apply_fact_fields(
        self,
        db_connected: Optional[bool] = None,
        db_latency_ms: Optional[float] = None,
        task_count: Optional[int] = None,
        vram_allocated_gb: Optional[float] = None,
        vram_total_gb: Optional[float] = None,
        status_message: Optional[str] = None,
    ) -> None:
        if db_connected is not None:
            self.set_db_status(db_connected, db_latency_ms)
        elif db_latency_ms is not None:
            self.set_db_status(True, db_latency_ms)

        if task_count is not None:
            self.set_task_count(task_count)

        if vram_allocated_gb is not None or vram_total_gb is not None:
            self.set_vram_status(vram_allocated_gb, vram_total_gb)

        if status_message is not None:
            self.set_status_message(status_message)

    def _build_ui(self) -> None:
        # Left status text area
        self._status_label = QLabel('Ready // 待機中')
        self._status_label.setStyleSheet(qss("telemetry_status_label"))
        self.addWidget(self._status_label, 1)

        # Right Telemetry Chips
        chip_container = QWidget()
        chip_layout = QHBoxLayout(chip_container)
        chip_layout.setContentsMargins(0, 0, 6, 0)
        chip_layout.setSpacing(6)

        # 1. Database connection chip
        self.db_chip = QLabel('🟢 DB: Ready')
        self.db_chip.setStyleSheet(qss("telemetry_db_ok"))
        self.db_chip.setToolTip('PostgreSQL + pgvector connection status')
        chip_layout.addWidget(self.db_chip)

        # 2. GPU / VRAM usage chip
        self.gpu_chip = QLabel('⚡ VRAM: --')
        self.gpu_chip.setStyleSheet(qss("telemetry_gpu_chip"))
        self.gpu_chip.setToolTip('GPU Compute & VRAM telemetry')
        chip_layout.addWidget(self.gpu_chip)

        # 3. Worker task status
        self.task_chip = QLabel('🔄 Tasks: 0')
        self.task_chip.setStyleSheet(qss("telemetry_task_idle"))
        self.task_chip.setToolTip('Active background tasks & workers')
        chip_layout.addWidget(self.task_chip)

        # 4. Layout switcher button chip
        self.layout_btn = QPushButton('☰ Nav')
        self.layout_btn.setStyleSheet(qss("telemetry_layout_btn"))
        self.layout_btn.setToolTip('Toggle Navigation Mode (Rail vs. Top Bar, Ctrl+Shift+L)')
        self.layout_btn.clicked.connect(self.layout_toggle_requested.emit)
        chip_layout.addWidget(self.layout_btn)

        self.addPermanentWidget(chip_container)

    def set_status_message(self, message: str, timeout_ms: int = 4000) -> None:
        self._status_label.setText(message)
        self._status_reset_timer.stop()
        if timeout_ms > 0:
            self._status_reset_timer.start(timeout_ms)

    def showMessage(self, message: str, timeout: int = 0) -> None:
        """Override QStatusBar.showMessage to update the styled status label."""
        self.set_status_message(message, timeout_ms=timeout)

    def _reset_status_message(self) -> None:
        self._status_label.setText('Ready // 待機中')

    def set_db_status(self, connected: bool, latency_ms: Optional[float] = None) -> None:
        if connected:
            text = f'🟢 DB: {latency_ms:.0f}ms' if latency_ms is not None else '🟢 DB: Ready'
            self.db_chip.setText(text)
            self.db_chip.setStyleSheet(qss("telemetry_db_ok"))
        else:
            self.db_chip.setText('🔴 DB: Disconnected')
            self.db_chip.setStyleSheet(qss("telemetry_db_err"))

    def set_task_count(self, count: int) -> None:
        if count > 0:
            self.task_chip.setText(f'🔄 Tasks: {count}')
            self.task_chip.setStyleSheet(qss("telemetry_task_busy"))
        else:
            self.task_chip.setText('🔄 Tasks: 0')
            self.task_chip.setStyleSheet(qss("telemetry_task_idle"))

    def set_vram_status(self, allocated_gb: Optional[float], total_gb: Optional[float]) -> None:
        if allocated_gb is not None and total_gb is not None:
            self.gpu_chip.setText(f'⚡ VRAM: {allocated_gb:.1f}/{total_gb:.1f} GB')
        elif allocated_gb is not None:
            self.gpu_chip.setText(f'⚡ VRAM: {allocated_gb:.1f} GB')
        else:
            self.gpu_chip.setText('⚡ VRAM: --')

    def _sample_telemetry(self) -> None:
        if self._disposed:
            return
        # GPU / Compute
        try:
            import torch

            if torch.cuda.is_available():
                alloc = torch.cuda.memory_allocated() / (1024**3)
                total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                self.set_vram_status(alloc, total)
            else:
                self.gpu_chip.setText('⚡ CPU Mode')
        except Exception:
            self.gpu_chip.setText('⚡ CPU Mode')

        # Database service via ModuleContext (non-widget service)
        if self._context is not None and self._context.services.has(LIBRARY_DATABASE_SERVICE):
            db_svc = self._context.services.get(LIBRARY_DATABASE_SERVICE)
            if db_svc is not None and getattr(db_svc, 'db', None) is not None:
                self.set_db_status(True)

    def dispose(self) -> None:
        """Clean up timers and subscriptions on shutdown."""
        self._disposed = True
        if hasattr(self, '_timer') and self._timer is not None:
            self._timer.stop()
        if hasattr(self, '_initial_sample_timer') and self._initial_sample_timer is not None:
            self._initial_sample_timer.stop()
        if hasattr(self, '_coalesce_timer') and self._coalesce_timer is not None:
            self._coalesce_timer.stop()
        if hasattr(self, '_status_reset_timer') and self._status_reset_timer is not None:
            self._status_reset_timer.stop()
        for sub in self._subscriptions:
            sub.disconnect()
        self._subscriptions.clear()
        self._event_hub = None


__all__ = ['TelemetryStatusBar', 'create_telemetry_bridge']
