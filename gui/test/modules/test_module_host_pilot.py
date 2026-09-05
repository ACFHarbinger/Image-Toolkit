"""gui/test/modules/test_module_host_pilot.py
=========================================
Unit tests for ModuleDescriptor, ModuleRegistry, ModuleHost, and Log Panel pilot (§1.3, #527).
"""

from __future__ import annotations

from gui.src.modules import (
    ConstructionPolicy,
    ModuleCategory,
    ModuleDescriptor,
    ModuleHostWidget,
    ModuleRegistry,
    ModuleRoute,
    create_log_panel_descriptor,
)
from PySide6.QtWidgets import QLabel


class TestModuleDescriptor:
    """Verify descriptor metadata, lifecycle, and child routes."""

    def test_lazy_widget_instantiation(self, q_app):
        call_count = 0

        def _factory():
            nonlocal call_count
            call_count += 1
            return QLabel("Lazy Widget")

        desc = ModuleDescriptor(
            id="test_mod",
            title="Test Module",
            category=ModuleCategory.SYSTEM,
            construction_policy=ConstructionPolicy.LAZY,
            view_factory=_factory,
            singleton=True,
            child_routes=[
                ModuleRoute("sub1", "Subroute 1"),
                ModuleRoute("sub2", "Subroute 2"),
            ],
        )

        assert call_count == 0
        w1 = desc.get_widget()
        assert call_count == 1
        w2 = desc.get_widget()
        assert call_count == 1
        assert w1 is w2

        assert desc.has_child_route("sub1") is True
        assert desc.has_child_route("nonexistent") is False
        assert desc.get_child_route("sub2").title == "Subroute 2"


class TestModuleRegistry:
    """Verify registry queries, filtering, and route resolution."""

    def test_registration_and_queries(self):
        reg = ModuleRegistry()
        m1 = ModuleDescriptor(
            id="mod1",
            title="Image Finder",
            category=ModuleCategory.LIBRARY,
            order_index=20,
        )
        m2 = ModuleDescriptor(
            id="mod2",
            title="Log Viewer",
            category=ModuleCategory.DEVELOPER,
            order_index=10,
        )

        reg.register(m1)
        reg.register(m2)

        assert [m.id for m in reg.all_modules()] == ["mod2", "mod1"]
        assert len(reg.by_category(ModuleCategory.LIBRARY)) == 1
        assert reg.by_category(ModuleCategory.LIBRARY)[0].id == "mod1"
        assert len(reg.search("Finder")) == 1

    def test_route_resolution(self):
        reg = ModuleRegistry()
        desc = ModuleDescriptor(
            id="stitch",
            title="Stitch Workspace",
            category=ModuleCategory.STITCHING,
            child_routes=[
                ModuleRoute("registration", "Registration"),
                ModuleRoute("seam", "Seam Painter"),
            ],
        )
        reg.register(desc)

        # Top-level route
        d, r = reg.resolve_route("stitch")
        assert d is desc
        assert r is None

        # Child route
        d, r = reg.resolve_route("stitch/seam")
        assert d is desc
        assert r is not None
        assert r.route_id == "seam"

        # Invalid child route -- must read as "no match" entirely (#527
        # cross-review), not resolve to the top-level module as if no
        # child had been requested.
        d, r = reg.resolve_route("stitch/unknown")
        assert d is None
        assert r is None

        # Non-existent module
        d, r = reg.resolve_route("missing/route")
        assert d is None
        assert r is None


class TestModuleHostWidget:
    """Verify host container lifecycle, lazy mounting, and routing signals."""

    def test_lazy_mounting_and_navigation(self, q_app):
        host = ModuleHostWidget()
        factory_runs = 0

        def _factory():
            nonlocal factory_runs
            factory_runs += 1
            return QLabel("Hosted View")

        desc = ModuleDescriptor(
            id="pilot_mod",
            title="Pilot Module",
            category=ModuleCategory.SYSTEM,
            construction_policy=ConstructionPolicy.LAZY,
            view_factory=_factory,
            child_routes=[ModuleRoute("sub", "Sub Route")],
        )

        host.register_module(desc)
        assert not host.is_mounted("pilot_mod")
        assert factory_runs == 0

        # Spy on signals
        nav_events = []
        change_events = []
        host.module_navigated.connect(lambda mod_id, route: nav_events.append((mod_id, route)))
        host.module_changed.connect(lambda mod_id: change_events.append(mod_id))

        # First navigation triggers construction and mounting
        widget = host.navigate_to("pilot_mod")
        assert widget is not None
        assert host.is_mounted("pilot_mod")
        assert factory_runs == 1
        assert host.active_module_id == "pilot_mod"
        assert host.active_route == "pilot_mod"
        assert len(change_events) == 1
        assert len(nav_events) == 1

        # Navigation to child route reuses widget without re-instantiation
        widget2 = host.navigate_to("pilot_mod/sub")
        assert widget2 is widget
        assert factory_runs == 1
        assert host.active_route == "pilot_mod/sub"
        # module_changed should not fire again since module_id is same
        assert len(change_events) == 1
        assert len(nav_events) == 2

    def test_unknown_child_route_does_not_navigate(self, q_app):
        """#527 cross-review: navigating to an unresolvable child route
        must be a no-op -- it must not mount/activate the module as if
        the invalid route were valid.
        """
        host = ModuleHostWidget()
        desc = ModuleDescriptor(
            id="pilot_mod",
            title="Pilot Module",
            category=ModuleCategory.SYSTEM,
            construction_policy=ConstructionPolicy.LAZY,
            view_factory=lambda: QLabel("Hosted View"),
            child_routes=[ModuleRoute("sub", "Sub Route")],
        )
        host.register_module(desc)

        nav_events = []
        host.module_navigated.connect(lambda mod_id, route: nav_events.append((mod_id, route)))

        result = host.navigate_to("pilot_mod/nonexistent")
        assert result is None
        assert not host.is_mounted("pilot_mod")
        assert host.active_module_id is None
        assert nav_events == []


class TestLogPanelPilot:
    """Verify Log Panel pilot integration with ModuleDescriptor and ModuleHost."""

    def test_log_panel_pilot_descriptor_and_hosting(self, q_app):
        desc = create_log_panel_descriptor(tab_name="Test System Log")
        assert desc.id == "log_panel"
        assert desc.category == ModuleCategory.DEVELOPER
        assert desc.has_child_route("system") is True
        assert desc.has_child_route("crawlers") is True

        host = ModuleHostWidget()
        host.register_module(desc)
        assert not host.is_mounted("log_panel")

        # Mount log panel into host via route
        widget = host.navigate_to("log_panel/system")
        assert widget is not None
        assert host.is_mounted("log_panel")
        from gui.src.windows.logging.log_window import LogWindow

        assert isinstance(widget, LogWindow)
        # Verify log functionality works inside the host
        widget.append_log("Diagnostic test message", level="INFO")
        assert "Diagnostic test message" in widget.log_output.toPlainText()
