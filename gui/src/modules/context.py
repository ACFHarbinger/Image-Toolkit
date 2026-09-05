"""Non-visual dependencies supplied to module factories."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Hashable

from PySide6.QtWidgets import QWidget

from .events import EventHub


class ModuleServices:
    """App-owned service registry; widgets are deliberately not services."""

    def __init__(self) -> None:
        self._services: dict[Hashable, Any] = {}

    def register(self, key: Hashable, service: Any) -> None:
        if isinstance(service, QWidget):
            raise TypeError("Module services must not expose QWidget instances")
        if key in self._services:
            raise ValueError(f"Service already registered: {key!r}")
        self._services[key] = service

    def require(self, key: Hashable) -> Any:
        try:
            return self._services[key]
        except KeyError as exc:
            raise LookupError(f"Required module service is unavailable: {key!r}") from exc

    def get(self, key: Hashable, default: Any = None) -> Any:
        return self._services.get(key, default)


@dataclass(frozen=True, slots=True)
class ModuleContext:
    """Factory context for one application/account session."""

    event_hub: EventHub
    services: ModuleServices
    account_id: str | None = None


__all__ = ["ModuleContext", "ModuleServices"]
