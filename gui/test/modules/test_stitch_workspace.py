"""Image Stitching's shared-host workspace contract (#512)."""

from __future__ import annotations

import sys
import types

from gui.src.modules.catalog import ModuleCatalog
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.events import EventHub
from gui.src.modules.runtime import ModuleRuntime
from gui.src.modules.stitch_workspace import (
    STITCH_ROUTES,
    STITCH_WORKSPACE_ID,
    register_stitch_workspace,
)
from PySide6.QtWidgets import QTabWidget, QWidget


class FakeStitchTab(QWidget):
    constructions = 0

    def __init__(self) -> None:
        super().__init__()
        type(self).constructions += 1
        self._tab_widget = QTabWidget(self)
        for _module_id, _route_key, title in STITCH_ROUTES:
            self._tab_widget.addTab(QWidget(), title)


def _runtime(q_app, monkeypatch) -> ModuleRuntime:
    FakeStitchTab.constructions = 0
    monkeypatch.setitem(sys.modules, "asp_gui", types.ModuleType("asp_gui"))
    elements = types.ModuleType("asp_gui.elements")
    elements.StitchTab = FakeStitchTab
    monkeypatch.setitem(sys.modules, "asp_gui.elements", elements)
    catalog = ModuleCatalog()
    assert register_stitch_workspace(catalog, enabled=True)
    context = ModuleContext(event_hub=EventHub(q_app), services=ModuleServices())
    return ModuleRuntime(catalog, context)


def test_workspace_feature_flag_can_leave_catalog_unchanged():
    catalog = ModuleCatalog()

    assert register_stitch_workspace(catalog, enabled=False) is False
    assert catalog.all_descriptors() == ()


def test_stitch_routes_share_one_lazy_host(q_app, monkeypatch):
    runtime = _runtime(q_app, monkeypatch)

    handles = [runtime.activate(module_id) for module_id, _route_key, _title in STITCH_ROUTES]

    assert FakeStitchTab.constructions == 1
    assert all(handle is handles[0] for handle in handles)
    assert runtime.active_module_id == STITCH_ROUTES[-1][0]


def test_stitch_route_activation_selects_the_matching_internal_panel(q_app, monkeypatch):
    runtime = _runtime(q_app, monkeypatch)

    handle = runtime.activate("stitch.canvas")

    assert handle.widget._tab_widget.currentIndex() == 3
    assert runtime.catalog.require_workspace(STITCH_WORKSPACE_ID).module_id == STITCH_WORKSPACE_ID
