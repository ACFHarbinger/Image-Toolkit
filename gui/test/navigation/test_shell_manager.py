"""Tests for ShellLayoutManager / rail / ribbon (#536).

Crash-class contracts: constructing chrome must not mount modules;
category paint must not activate; mount happens before ModuleActivated.
"""

from __future__ import annotations

import pytest
from gui.src.components.navigation import (
    NavigationRailWidget,
    ShellLayoutManager,
    ShellNavMode,
    TopSegmentedRibbonWidget,
)
from gui.src.modules.catalog import ModuleCatalog, PageDescriptor, RouteDescriptor, WorkspaceDescriptor
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.descriptor import ModuleCategory
from gui.src.modules.events import EventHub, ModuleActivated, NavigateIntent
from gui.src.modules.runtime import ModuleRuntime, WidgetHandle
from PySide6.QtWidgets import QLabel, QWidget

pytestmark = pytest.mark.gui


class CountingHandle(WidgetHandle):
    def __init__(self, label: str) -> None:
        super().__init__(QLabel(label))
        self.label = label
        self.activations: list[str | None] = []

    def activate(self, route_key: str | None = None) -> None:
        self.activations.append(route_key)


@pytest.fixture
def sample_catalog():
    cat = ModuleCatalog()
    calls: dict[str, int] = {}

    def factory(mod_id: str):
        def _factory(_ctx):
            calls[mod_id] = calls.get(mod_id, 0) + 1
            return CountingHandle(mod_id)

        return _factory

    cat.register(
        PageDescriptor(
            module_id="system.convert",
            title="Convert",
            category=ModuleCategory.SYSTEM,
            factory=factory("system.convert"),
        )
    )
    cat.register(
        PageDescriptor(
            module_id="system.merge",
            title="Merge",
            category=ModuleCategory.SYSTEM,
            factory=factory("system.merge"),
        )
    )
    cat.register(
        PageDescriptor(
            module_id="library.search",
            title="Search",
            category=ModuleCategory.LIBRARY,
            factory=factory("library.search"),
        )
    )
    cat.register(
        WorkspaceDescriptor(
            module_id="stitch",
            title="Stitch",
            category=ModuleCategory.STITCHING,
            factory=factory("stitch"),
        )
    )
    cat.register(
        RouteDescriptor(
            module_id="stitch.graph",
            workspace_id="stitch",
            route_key="graph",
            title="Graph",
            category=ModuleCategory.STITCHING,
        )
    )
    cat._factory_calls = calls  # type: ignore[attr-defined]
    return cat


@pytest.fixture
def sample_runtime(sample_catalog, q_app):
    ctx = ModuleContext(event_hub=EventHub(q_app), services=ModuleServices())
    return ModuleRuntime(sample_catalog, ctx)


class TestShellNavigation:
    def test_shell_construct_does_not_mount(self, q_app, sample_runtime, sample_catalog):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container)

        assert manager.stack.count() == 0
        assert manager.active_module_id is None
        assert sample_catalog._factory_calls == {}  # type: ignore[attr-defined]
        assert not sample_runtime.is_created("system.convert")

    def test_category_select_does_not_activate(self, q_app, sample_runtime, sample_catalog):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container)
        selected: list[str] = []
        manager.rail.module_selected.connect(selected.append)

        manager.rail.select_category(ModuleCategory.LIBRARY)
        assert manager.rail.active_category == ModuleCategory.LIBRARY
        assert selected == []
        assert manager.stack.count() == 0
        assert sample_catalog._factory_calls == {}  # type: ignore[attr-defined]

        manager.ribbon._populate_category(ModuleCategory.LIBRARY)
        assert manager.ribbon.active_category == ModuleCategory.LIBRARY
        assert manager.stack.count() == 0

    def test_shell_lazy_mounting_and_mode_toggle(self, q_app, sample_runtime):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container, default_mode=ShellNavMode.RAIL)
        container.show()

        assert manager.nav_mode == ShellNavMode.RAIL
        assert not manager.rail.isHidden()
        assert manager.ribbon.isHidden()

        manager.activate_module("system.convert")
        assert manager.stack.count() == 1
        assert manager.active_module_id == "system.convert"
        assert sample_runtime.is_created("system.convert")
        assert not sample_runtime.is_created("library.search")

        manager.activate_module("library.search")
        assert manager.stack.count() == 2
        assert manager.active_module_id == "library.search"

        manager.toggle_nav_mode()
        assert manager.nav_mode == ShellNavMode.TOP_BAR
        assert manager.rail.isHidden()
        assert not manager.ribbon.isHidden()

    def test_module_activated_after_mount(self, q_app, sample_runtime):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container)
        seen: list[tuple[str, int]] = []

        def _on_activated(fact: ModuleActivated) -> None:
            seen.append((fact.module_id, manager.stack.count()))

        sample_runtime.context.event_hub.subscribe(ModuleActivated, _on_activated, owner=manager)
        manager.activate_module("system.convert")

        assert seen == [("system.convert", 1)]
        assert manager.stack.currentWidget() is not None

    def test_navigate_intent_forwards_route_key(self, q_app, sample_runtime):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container)

        sample_runtime.context.event_hub.publish(
            NavigateIntent(origin="test", module_id="stitch", route_key="graph")
        )
        assert manager.active_module_id == "stitch.graph"
        assert sample_runtime.is_created("stitch")
        handle = sample_runtime.handle_for("stitch")
        assert isinstance(handle, CountingHandle)
        assert handle.activations == ["graph"]

    def test_clear_mounted_before_dispose(self, q_app, sample_runtime):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container)
        manager.activate_module("system.convert")
        assert manager.stack.count() == 1

        manager.clear_mounted()
        assert manager.stack.count() == 0
        assert manager.active_module_id is None
        sample_runtime.dispose()
        assert not sample_runtime.is_created("system.convert")

    def test_navigable_excludes_workspace_host(self, sample_catalog):
        ids = [d.module_id for d in sample_catalog.navigable_by_category(ModuleCategory.STITCHING)]
        assert ids == ["stitch.graph"]
        assert "stitch" not in ids

    def test_rail_and_ribbon_paint_only(self, q_app, sample_catalog):
        rail = NavigationRailWidget(sample_catalog)
        ribbon = TopSegmentedRibbonWidget(sample_catalog)
        rail_hits: list[str] = []
        ribbon_hits: list[str] = []
        rail.module_selected.connect(rail_hits.append)
        ribbon.module_selected.connect(ribbon_hits.append)

        rail.select_category(ModuleCategory.SYSTEM)
        ribbon._populate_category(ModuleCategory.SYSTEM)
        assert rail_hits == []
        assert ribbon_hits == []

        rail.set_active_module("system.merge")
        ribbon.set_active_module("system.merge")
        assert rail.active_module_id == "system.merge"
        assert ribbon.active_module_id == "system.merge"
        assert rail_hits == []
        assert ribbon_hits == []
