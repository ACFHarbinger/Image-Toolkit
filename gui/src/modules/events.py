"""Versioned GUI-thread intents and facts for module coordination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, TypeVar
from uuid import uuid4

from PySide6.QtCore import QObject, QThread, Signal


@dataclass(frozen=True, kw_only=True, slots=True)
class ModuleEvent:
    """Shared envelope for domain-owned event schemas."""

    origin: str
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: int = 1


@dataclass(frozen=True, kw_only=True, slots=True)
class Intent(ModuleEvent):
    """A command for a shell or domain controller."""


@dataclass(frozen=True, kw_only=True, slots=True)
class Fact(ModuleEvent):
    """A completed state change broadcast to interested modules."""


@dataclass(frozen=True, kw_only=True, slots=True)
class NavigateIntent(Intent):
    module_id: str
    route_key: str | None = None
    state: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class ModuleActivated(Fact):
    module_id: str
    route_key: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ModuleDeactivated(Fact):
    module_id: str


@dataclass(frozen=True, kw_only=True, slots=True)
class SelectionChangedFact(Fact):
    paths: tuple[str, ...] = ()
    active_path: str | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class InspectImageIntent(Intent):
    file_path: str
    resolution: tuple[int, int] | None = None
    tags: tuple[tuple[str, tuple[str, ...]], ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, kw_only=True, slots=True)
class ToggleInspectorIntent(Intent):
    visible: bool | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class TelemetryUpdatedFact(Fact):
    db_connected: bool | None = None
    db_latency_ms: float | None = None
    task_count: int | None = None
    vram_allocated_gb: float | None = None
    vram_total_gb: float | None = None
    status_message: str | None = None
class DatabaseAvailabilityChanged(Fact):
    connected: bool


@dataclass(frozen=True, kw_only=True, slots=True)
class TagCatalogChanged(Fact):
    """Tags or categories changed; consumers should rebuild their filters."""


@dataclass(frozen=True, kw_only=True, slots=True)
class GroupCatalogChanged(Fact):
    groups: tuple[str, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class SubgroupCatalogChanged(Fact):
    subgroups: tuple[tuple[str, str], ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class FilterByTagIntent(Intent):
    module_id: str
    tag_name: str


@dataclass(frozen=True, kw_only=True, slots=True)
class ImportPathsIntent(Intent):
    module_id: str
    paths: tuple[str, ...]


EventT = TypeVar("EventT", bound=ModuleEvent)


class EventSubscription:
    """Lifecycle-owned callback registration."""

    def __init__(self, hub: EventHub, event_type: type[ModuleEvent], callback: Callable[[ModuleEvent], None]) -> None:
        self._hub = hub
        self._event_type = event_type
        self._callback = callback
        self._connected = True

    def disconnect(self) -> None:
        if self._connected:
            self._hub._unsubscribe(self._event_type, self._callback)
            self._connected = False


class EventHub(QObject):
    """App-owned, GUI-thread event hub for intents and facts only."""

    published = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._subscribers: dict[type[ModuleEvent], list[Callable[[ModuleEvent], None]]] = {}

    def subscribe(
        self,
        event_type: type[EventT],
        callback: Callable[[EventT], None],
        *,
        owner: QObject | None = None,
    ) -> EventSubscription:
        self._subscribers.setdefault(event_type, []).append(callback)  # type: ignore[arg-type]
        subscription = EventSubscription(self, event_type, callback)  # type: ignore[arg-type]
        if owner is not None:
            owner.destroyed.connect(lambda: subscription.disconnect())
        return subscription

    def publish(self, event: ModuleEvent) -> None:
        if QThread.currentThread() is not self.thread():
            raise RuntimeError("EventHub.publish() must run on its owning GUI thread")
        if not isinstance(event, (Intent, Fact)):
            raise TypeError("EventHub accepts Intent and Fact events only; use a typed service for requests")
        self.published.emit(event)
        for event_type, callbacks in tuple(self._subscribers.items()):
            if isinstance(event, event_type):
                for callback in tuple(callbacks):
                    callback(event)

    def _unsubscribe(self, event_type: type[ModuleEvent], callback: Callable[[ModuleEvent], None]) -> None:
        callbacks = self._subscribers.get(event_type)
        if callbacks is None:
            return
        try:
            callbacks.remove(callback)
        except ValueError:
            return
        if not callbacks:
            self._subscribers.pop(event_type, None)


__all__ = [
    "EventHub",
    "EventSubscription",
    "DatabaseAvailabilityChanged",
    "Fact",
    "InspectImageIntent",
    "FilterByTagIntent",
    "GroupCatalogChanged",
    "ImportPathsIntent",
    "Intent",
    "ModuleActivated",
    "ModuleDeactivated",
    "ModuleEvent",
    "NavigateIntent",
    "SelectionChangedFact",
    "TelemetryUpdatedFact",
    "ToggleInspectorIntent",
    "SubgroupCatalogChanged",
    "TagCatalogChanged",
]
