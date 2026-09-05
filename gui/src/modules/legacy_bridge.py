"""Temporary adapter from legacy navigation callbacks to typed intents."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject

from .events import EventHub, EventSubscription, NavigateIntent


class LegacyNavigationBridge:
    """Lets an old tab request navigation without retaining a target widget."""

    def __init__(self, event_hub: EventHub, origin: str) -> None:
        self._event_hub = event_hub
        self._origin = origin

    def navigate(
        self,
        module_id: str,
        route_key: str | None = None,
        state: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self._event_hub.publish(
            NavigateIntent(
                origin=self._origin,
                module_id=module_id,
                route_key=route_key,
                state=state,
            )
        )

    def on_navigation(
        self,
        callback: Callable[[NavigateIntent], None],
        *,
        owner: QObject | None = None,
    ) -> EventSubscription:
        return self._event_hub.subscribe(NavigateIntent, callback, owner=owner)


__all__ = ["LegacyNavigationBridge"]
