"""Image Stitching's shared-host workspace contract (#535).

Asserts the issue bar: no route constructs a second StitchTab, and
activate() selects the named panel rather than a magic tab index.
"""

from __future__ import annotations

import sys
import types

import pytest
from gui.src.modules.catalog import ModuleCatalog
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.events import EventHub
from gui.src.modules.runtime import ModuleRuntime
from gui.src.modules.stitch_workspace import (
    STITCH_ROUTES,
    STITCH_WORKSPACE_ID,
    create_stitch_workspace,
    register_stitch_workspace,
)
from gui.src.preferences import MemoryPreferenceAdapter, PreferenceScope, PreferenceStore, PrefKeys
from PySide6.QtWidgets import QTabWidget, QWidget


class FakeStitchTab(QWidget):
    constructions = 0

    def __init__(self) -> None:
        super().__init__()
        type(self).constructions += 1
        self._tab_widget = QTabWidget(self)
        self.stitch_panel = QWidget()
        self.graph_panel = QWidget()
        self.adjust_panel = QWidget()
        self.canvas_panel = QWidget()
        self.stats_panel = QWidget()
        self.seq_builder_panel = QWidget()
        self.hybrid_stitch_panel = QWidget()
        self.anim_clusters_panel = QWidget()
        # Add in reverse inventory order so a magic STITCH_ROUTES index
        # would select the wrong panel (issue #535 audit landmine).
        for _module_id, _route_key, title, panel_attr in reversed(STITCH_ROUTES):
            self._tab_widget.addTab(getattr(self, panel_attr), title)


def _patch_stitch_tab(monkeypatch) -> None:
    FakeStitchTab.constructions = 0
    monkeypatch.setitem(sys.modules, "asp_gui", types.ModuleType("asp_gui"))
    elements = types.ModuleType("asp_gui.elements")
    elements.StitchTab = FakeStitchTab
    monkeypatch.setitem(sys.modules, "asp_gui.elements", elements)


def _runtime(q_app, monkeypatch) -> ModuleRuntime:
    _patch_stitch_tab(monkeypatch)
    catalog = ModuleCatalog()
    assert register_stitch_workspace(catalog, enabled=True)
    context = ModuleContext(event_hub=EventHub(q_app), services=ModuleServices())
    return ModuleRuntime(catalog, context)


def test_workspace_stays_unregistered_when_account_flag_is_off():
    store = PreferenceStore(lazy_adapters=True)
    store.register_adapter(PreferenceScope.ACCOUNT, MemoryPreferenceAdapter())
    catalog = ModuleCatalog()

    assert store.get(PrefKeys.EXPERIMENTAL_STITCH_WORKSPACE) is False
    assert register_stitch_workspace(catalog, preference_store=store) is False
    assert catalog.all_descriptors() == ()


def test_all_eight_routes_share_one_lazy_host(q_app, monkeypatch):
    runtime = _runtime(q_app, monkeypatch)

    handles = [
        runtime.activate(module_id) for module_id, _route_key, _title, _panel in STITCH_ROUTES
    ]

    assert FakeStitchTab.constructions == 1
    assert all(handle is handles[0] for handle in handles)
    assert runtime.active_module_id == STITCH_ROUTES[-1][0]
    assert runtime.catalog.require_workspace(STITCH_WORKSPACE_ID).module_id == STITCH_WORKSPACE_ID


def test_route_activation_selects_named_panel_not_inventory_index(q_app, monkeypatch):
    runtime = _runtime(q_app, monkeypatch)

    handle = runtime.activate("stitch.canvas")
    tab = handle.widget._tab_widget

    assert handle.widget.constructions == 1
    assert tab.currentWidget() is handle.widget.canvas_panel
    assert tab.currentIndex() != 3, "magic STITCH_ROUTES index would have been 3"

    runtime.activate("stitch.stitch")
    assert tab.currentWidget() is handle.widget.stitch_panel


def test_unknown_stitch_route_fails_loud(q_app, monkeypatch):
    _patch_stitch_tab(monkeypatch)
    handle = create_stitch_workspace(None)  # type: ignore[arg-type]
    with pytest.raises(LookupError, match="Unknown Stitch workspace route"):
        handle.activate("not-a-panel")


def test_create_stitch_workspace_does_not_run_until_called(monkeypatch):
    _patch_stitch_tab(monkeypatch)
    assert FakeStitchTab.constructions == 0
    create_stitch_workspace(None)  # type: ignore[arg-type]
    assert FakeStitchTab.constructions == 1
