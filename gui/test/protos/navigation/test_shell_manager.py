"""Tests for NavigationRailWidget, TopSegmentedRibbonWidget, and ShellLayoutManager (§2.36)."""

from __future__ import annotations

import pytest
from gui.src.protos.modules.descriptor import ModuleCategory, ModuleDescriptor
from gui.src.protos.modules.registry import ModuleRegistry
from gui.src.protos.navigation import (
    NavigationRailWidget,
    ShellLayoutManager,
    ShellNavMode,
    TopSegmentedRibbonWidget,
)
from PySide6.QtWidgets import QLabel, QWidget

pytestmark = pytest.mark.gui


@pytest.fixture
def sample_registry():
    reg = ModuleRegistry()
    reg.clear()
    reg.register(
        ModuleDescriptor(
            id="sys.convert",
            title="Convert",
            category=ModuleCategory.SYSTEM,
            japanese_subtext="変換",
            view_factory=lambda: QLabel("Convert View"),
        )
    )
    reg.register(
        ModuleDescriptor(
            id="sys.merge",
            title="Merge",
            category=ModuleCategory.SYSTEM,
            japanese_subtext="結合",
            view_factory=lambda: QLabel("Merge View"),
        )
    )
    reg.register(
        ModuleDescriptor(
            id="lib.search",
            title="Search",
            category=ModuleCategory.LIBRARY,
            japanese_subtext="検索",
            view_factory=lambda: QLabel("Search View"),
        )
    )
    return reg


class TestShellNavigation:
    def test_navigation_rail_selection(self, q_app, sample_registry):
        rail = NavigationRailWidget(sample_registry)
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

    def test_top_segmented_ribbon(self, q_app, sample_registry):
        ribbon = TopSegmentedRibbonWidget(sample_registry)
        selected = []
        ribbon.module_selected.connect(selected.append)

        ribbon.set_active_module("lib.search")
        assert ribbon.active_module_id == "lib.search"
        assert ribbon.active_category == ModuleCategory.LIBRARY

    def test_shell_layout_manager_mode_switching(self, q_app, sample_registry):
        container = QWidget()
        manager = ShellLayoutManager(sample_registry, container, default_mode=ShellNavMode.RAIL)
        container.show()

        assert manager.nav_mode == ShellNavMode.RAIL
        assert not manager.rail.isHidden()
        assert manager.ribbon.isHidden()

        # Toggle mode
        manager.toggle_nav_mode()
        assert manager.nav_mode == ShellNavMode.TOP_BAR
        assert manager.rail.isHidden()
        assert not manager.ribbon.isHidden()

    def test_shell_lazy_mounting(self, q_app, sample_registry):
        container = QWidget()
        manager = ShellLayoutManager(sample_registry, container)

        assert manager.stack.count() == 0
        manager.activate_module("sys.convert")
        assert manager.stack.count() == 1
        assert manager.active_module_id == "sys.convert"

        manager.activate_module("lib.search")
        assert manager.stack.count() == 2
        assert manager.active_module_id == "lib.search"
