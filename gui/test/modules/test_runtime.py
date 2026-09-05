"""Contracts for the app-owned lazy module runtime (#510)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from gui.src.modules.catalog import ModuleCatalog, PageDescriptor, RouteDescriptor, WorkspaceDescriptor
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.descriptor import ModuleCategory
from gui.src.modules.events import EventHub, ModuleActivated, ModuleEvent, NavigateIntent
from gui.src.modules.legacy_bridge import LegacyNavigationBridge
from gui.src.modules.runtime import ModuleRuntime, WidgetHandle
from PySide6.QtWidgets import QLabel


class RecordingHandle(WidgetHandle):
    def __init__(self) -> None:
        super().__init__(QLabel())
        self.activations: list[str | None] = []
        self.deactivations = 0

    def activate(self, route_key: str | None = None) -> None:
        self.activations.append(route_key)

    def deactivate(self) -> None:
        self.deactivations += 1


def _context(q_app) -> ModuleContext:
    return ModuleContext(event_hub=EventHub(q_app), services=ModuleServices(), account_id="account-a")


def test_catalog_descriptors_are_immutable_and_routes_need_a_workspace():
    catalog = ModuleCatalog()
    page = PageDescriptor(
        module_id="database",
        title="Database",
        category=ModuleCategory.LIBRARY,
        factory=lambda context: WidgetHandle(QLabel()),
    )
    catalog.register(page)

    with pytest.raises(FrozenInstanceError):
        page.title = "Changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="requires registered workspace"):
        catalog.register(
            RouteDescriptor(
                module_id="stitch.adjust",
                workspace_id="stitch",
                route_key="adjust",
                title="Adjust",
                category=ModuleCategory.STITCHING,
            )
        )


def test_runtime_lazily_caches_pages_and_emits_facts(q_app):
    catalog = ModuleCatalog()
    created: list[RecordingHandle] = []
    catalog.register(
        PageDescriptor(
            module_id="database",
            title="Database",
            category=ModuleCategory.LIBRARY,
            factory=lambda context: created.append(RecordingHandle()) or created[-1],
        )
    )
    context = _context(q_app)
    observed: list[ModuleActivated] = []
    context.event_hub.subscribe(ModuleActivated, observed.append)
    runtime = ModuleRuntime(catalog, context)

    first = runtime.activate("database")
    second = runtime.activate("database")

    assert first is second
    assert len(created) == 1
    assert created[0].activations == [None, None]
    assert [event.module_id for event in observed] == ["database", "database"]


def test_workspace_routes_share_one_lifecycle_handle(q_app):
    catalog = ModuleCatalog()
    handles: list[RecordingHandle] = []
    catalog.register(
        WorkspaceDescriptor(
            module_id="stitch",
            title="Image Stitching",
            category=ModuleCategory.STITCHING,
            factory=lambda context: handles.append(RecordingHandle()) or handles[-1],
        )
    )
    for route_key in ("adjust", "canvas"):
        catalog.register(
            RouteDescriptor(
                module_id=f"stitch.{route_key}",
                workspace_id="stitch",
                route_key=route_key,
                title=route_key.title(),
                category=ModuleCategory.STITCHING,
            )
        )
    runtime = ModuleRuntime(catalog, _context(q_app))

    adjust = runtime.activate("stitch.adjust")
    canvas = runtime.activate("stitch.canvas")

    assert adjust is canvas
    assert len(handles) == 1
    assert handles[0].activations == ["adjust", "canvas"]
    assert handles[0].deactivations == 0


def test_module_services_reject_widget_coupling(q_app):
    services = ModuleServices()
    with pytest.raises(TypeError, match="must not expose QWidget"):
        services.register("database-tab", QLabel())


def test_event_hub_delivers_typed_intents_and_disconnects(q_app):
    hub = EventHub(q_app)
    received: list[NavigateIntent] = []
    subscription = hub.subscribe(NavigateIntent, received.append)

    hub.publish(NavigateIntent(origin="search", module_id="database", route_key="listing"))
    subscription.disconnect()
    hub.publish(NavigateIntent(origin="search", module_id="database"))

    assert [(event.module_id, event.route_key) for event in received] == [("database", "listing")]


def test_legacy_bridge_forwards_navigation_without_a_widget_reference(q_app):
    hub = EventHub(q_app)
    received: list[NavigateIntent] = []
    bridge = LegacyNavigationBridge(hub, origin="database-tab")
    bridge.on_navigation(received.append)

    bridge.navigate("scan-metadata", state=(("path", "/images"),))

    assert len(received) == 1
    assert received[0].origin == "database-tab"
    assert received[0].module_id == "scan-metadata"
    assert received[0].state == (("path", "/images"),)


def test_event_hub_rejects_request_like_base_events(q_app):
    with pytest.raises(TypeError, match="typed service"):
        EventHub(q_app).publish(ModuleEvent(origin="test"))


def test_factory_must_return_a_lifecycle_handle(q_app):
    catalog = ModuleCatalog()
    catalog.register(
        PageDescriptor(
            module_id="bad",
            title="Bad",
            category=ModuleCategory.SYSTEM,
            factory=lambda context: QLabel(),  # type: ignore[arg-type]
        )
    )
    with pytest.raises(TypeError, match="must return ModuleHandle"):
        ModuleRuntime(catalog, _context(q_app)).activate("bad")
