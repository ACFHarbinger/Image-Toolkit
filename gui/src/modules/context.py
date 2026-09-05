"""gui/src/modules/context.py
==========================
Non-visual dependencies supplied to module factories (§2.36, #533).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Hashable, Optional

from PySide6.QtWidgets import QWidget

from gui.src.preferences import PreferenceStore
from gui.src.windows.window_manager import WindowManager

from .events import EventHub


class ModuleServices:
    """App-owned service registry; widgets are deliberately not services."""

    def __init__(self) -> None:
        self._services: dict[Hashable, Any] = {}

    def register(self, key: Hashable, service: Any) -> None:
        """Register an application service. Raises TypeError if service is a QWidget."""
        if isinstance(service, QWidget):
            raise TypeError("Module services must not expose QWidget instances")
        if key in self._services:
            raise ValueError(f"Service already registered: {key!r}")
        self._services[key] = service

    def require(self, key: Hashable) -> Any:
        """Retrieve a registered service, raising LookupError if missing."""
        try:
            return self._services[key]
        except KeyError as exc:
            raise LookupError(f"Required module service is unavailable: {key!r}") from exc

    def get(self, key: Hashable, default: Any = None) -> Any:
        """Retrieve a service or return default if unregistered."""
        return self._services.get(key, default)

    def has(self, key: Hashable) -> bool:
        """Check if a service is registered."""
        return key in self._services

    def __contains__(self, key: Hashable) -> bool:
        return key in self._services


@dataclass(frozen=True, slots=True)
class ModuleContext:
    """Factory context provided to module and workspace factories."""

    event_hub: EventHub
    services: ModuleServices
    preference_store: PreferenceStore = field(default_factory=PreferenceStore.instance)
    window_manager: WindowManager = field(default_factory=WindowManager.instance)
    account_id: Optional[str] = None


__all__ = ["ModuleContext", "ModuleServices"]
