"""Tests for NavigationRailWidget, TopSegmentedRibbonWidget, and ShellLayoutManager with ModuleCatalog (§2.36, #513)."""

from __future__ import annotations

import pytest
from gui.src.components.navigation import (
    NavigationRailWidget,
    ShellLayoutManager,
    ShellNavMode,
    TopSegmentedRibbonWidget,
)
from gui.src.modules.catalog import ModuleCatalog, PageDescriptor
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.descriptor import ModuleCategory
from gui.src.modules.events import EventHub, NavigateIntent
from gui.src.modules.runtime import ModuleRuntime, WidgetHandle
from PySide6.QtWidgets import QLabel, QWidget

pytestmark = pytest.mark.gui


@pytest.fixture
def sample_catalog():
    cat = ModuleCatalog()
    cat.register(
        PageDescriptor(
            module_id="sys.convert",
            title="Convert",
            category=ModuleCategory.SYSTEM,
            factory=lambda ctx: WidgetHandle(QLabel("Convert View")),
        )
    )
    cat.register(
        PageDescriptor(
            module_id="sys.merge",
            title="Merge",
            category=ModuleCategory.SYSTEM,
            factory=lambda ctx: WidgetHandle(QLabel("Merge View")),
        )
    )
    cat.register(
        PageDescriptor(
            module_id="lib.search",
            title="Search",
            category=ModuleCategory.LIBRARY,
            factory=lambda ctx: WidgetHandle(QLabel("Search View")),
        )
    )
    return cat


@pytest.fixture
def sample_context(q_app):
    return ModuleContext(event_hub=EventHub(), services=ModuleServices())


@pytest.fixture
def sample_runtime(sample_catalog, sample_context):
    return ModuleRuntime(sample_catalog, sample_context)


class TestShellNavigation:
    def test_navigation_rail_selection(self, q_app, sample_catalog):
        rail = NavigationRailWidget(sample_catalog)
        selected = []
        rail.module_selected.connect(selected.append)

        # Category switch updates drawer
        rail.select_category(ModuleCategory.LIBRARY)
        assert rail.active_category == ModuleCategory.LIBRARY
        assert selected
        assert selected[-1] == "lib.search"

        # Direct module selection
        rail.set_active_module("sys.convert")
        assert rail.active_category == ModuleCategory.SYSTEM
        assert rail.active_module_id == "sys.convert"

    def test_top_segmented_ribbon(self, q_app, sample_catalog):
        ribbon = TopSegmentedRibbonWidget(sample_catalog)
        selected = []
        ribbon.module_selected.connect(selected.append)

        ribbon.set_active_module("lib.search")
        assert ribbon.active_module_id == "lib.search"
        assert ribbon.active_category == ModuleCategory.LIBRARY

    def test_shell_layout_manager_mode_switching(self, q_app, sample_runtime):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container, default_mode=ShellNavMode.RAIL)
        container.show()

        assert manager.nav_mode == ShellNavMode.RAIL
        assert not manager.rail.isHidden()
        assert manager.ribbon.isHidden()

        # Toggle mode
        manager.toggle_nav_mode()
        assert manager.nav_mode == ShellNavMode.TOP_BAR
        assert manager.rail.isHidden()
        assert not manager.ribbon.isHidden()

    def test_shell_lazy_mounting(self, q_app, sample_runtime):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container)

        assert manager.stack.count() == 0
        manager.activate_module("sys.convert")
        assert manager.stack.count() == 1
        assert manager.active_module_id == "sys.convert"

        manager.activate_module("lib.search")
        assert manager.stack.count() == 2
        assert manager.active_module_id == "lib.search"

    def test_navigate_intent_activates_module(self, q_app, sample_runtime):
        container = QWidget()
        manager = ShellLayoutManager(sample_runtime, container)

        # Publish NavigateIntent on event hub
        sample_runtime.context.event_hub.publish(
            NavigateIntent(origin="test", module_id="lib.search")
        )
        assert manager.active_module_id == "lib.search"
        assert manager.stack.count() == 1
