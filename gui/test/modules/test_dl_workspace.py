"""Deep Learning workspace contract (#730) and Train handoff (#734)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from gui.src.modules.catalog import ModuleCatalog
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.dl_workspace import (
    DL_CLASSIC_ALIASES,
    DL_ROUTES,
    DL_WORKSPACE_ID,
    create_dl_workspace,
    register_dl_workspace,
)
from gui.src.modules.events import EventHub, ImportPathsIntent, NavigateIntent
from gui.src.modules.runtime import ModuleRuntime
from gui.src.preferences import MemoryPreferenceAdapter, PreferenceScope, PreferenceStore, PrefKeys
from gui.src.tabs.models.delta.lora_train_tab import (
    LoRATrainTab,
    dataset_folder_from_paths,
)
from PySide6.QtWidgets import QStackedWidget, QTabWidget, QWidget

pytestmark = pytest.mark.gui


class FakeDlHost(QWidget):
    constructions = 0

    def __init__(self, event_hub=None, parent=None) -> None:
        super().__init__(parent)
        type(self).constructions += 1
        self._pages: dict[str, QWidget] = {}
        self._stack = QStackedWidget(self)
        # Reverse inventory order so a magic DL_ROUTES index would pick wrong.
        for _module_id, route_key, _title in reversed(DL_ROUTES):
            page = QWidget()
            page.setObjectName(f"fake_{route_key}")
            self._pages[route_key] = page
            self._stack.addWidget(page)
        self.current_route: str | None = None

    def activate_route(self, route_key: str) -> None:
        page = self._pages.get(route_key)
        if page is None:
            raise LookupError(f"Unknown Deep Learning workspace route: {route_key}")
        self._stack.setCurrentWidget(page)
        self.current_route = route_key


def _patch_dl_host(monkeypatch) -> None:
    FakeDlHost.constructions = 0
    monkeypatch.setattr(
        "gui.src.tabs.models.dl_workspace_host.DeepLearningWorkspaceHost",
        FakeDlHost,
    )


def _runtime(q_app, monkeypatch) -> ModuleRuntime:
    _patch_dl_host(monkeypatch)
    catalog = ModuleCatalog()
    assert register_dl_workspace(catalog, enabled=True)
    context = ModuleContext(event_hub=EventHub(q_app), services=ModuleServices())
    return ModuleRuntime(catalog, context)


def test_workspace_stays_unregistered_when_account_flag_is_off():
    store = PreferenceStore(lazy_adapters=True)
    store.register_adapter(PreferenceScope.ACCOUNT, MemoryPreferenceAdapter())
    catalog = ModuleCatalog()

    assert store.get(PrefKeys.EXPERIMENTAL_DL_WORKSPACE) is False
    assert register_dl_workspace(catalog, preference_store=store) is False
    assert catalog.all_descriptors() == ()


def test_all_four_routes_share_one_lazy_host(q_app, monkeypatch):
    runtime = _runtime(q_app, monkeypatch)

    handles = [runtime.activate(module_id) for module_id, _route_key, _title in DL_ROUTES]

    assert FakeDlHost.constructions == 1
    assert all(handle is handles[0] for handle in handles)
    assert runtime.active_module_id == DL_ROUTES[-1][0]
    assert runtime.catalog.require_workspace(DL_WORKSPACE_ID).module_id == DL_WORKSPACE_ID


def test_route_activation_selects_named_page_not_inventory_index(q_app, monkeypatch):
    runtime = _runtime(q_app, monkeypatch)

    handle = runtime.activate("dl.generate")
    host = handle.widget

    assert host.constructions == 1
    assert host._stack.currentWidget() is host._pages["generate"]
    assert host._stack.currentIndex() != 1, "magic DL_ROUTES index would have been 1"
    assert not isinstance(host, QTabWidget)

    runtime.activate("dl.train")
    assert host._stack.currentWidget() is host._pages["train"]


def test_classic_ids_are_lookup_aliases_not_navigable_pills():
    catalog = ModuleCatalog()
    assert register_dl_workspace(catalog, enabled=True)

    navigable_ids = {descriptor.module_id for descriptor in catalog.navigable()}
    assert navigable_ids == {module_id for module_id, _route_key, _title in DL_ROUTES}
    for alias_id, target_id in DL_CLASSIC_ALIASES.items():
        assert catalog.get(alias_id) is catalog.require(target_id)
        assert alias_id not in navigable_ids


def test_unknown_dl_route_fails_loud(q_app, monkeypatch):
    _patch_dl_host(monkeypatch)
    handle = create_dl_workspace(None)  # type: ignore[arg-type]
    with pytest.raises(LookupError, match="Unknown Deep Learning workspace route"):
        handle.activate("not-a-panel")


def test_create_dl_workspace_does_not_run_until_called(monkeypatch):
    _patch_dl_host(monkeypatch)
    assert FakeDlHost.constructions == 0
    create_dl_workspace(None)  # type: ignore[arg-type]
    assert FakeDlHost.constructions == 1


def test_dataset_folder_from_paths_uses_directory_or_parent(tmp_path):
    folder = tmp_path / "frames"
    folder.mkdir()
    image = folder / "frame.png"
    image.write_bytes(b"x")

    assert dataset_folder_from_paths((str(folder),)) == str(folder)
    assert dataset_folder_from_paths((str(image),)) == str(folder)
    assert dataset_folder_from_paths(()) is None


def test_apply_imported_paths_sets_dataset_and_does_not_start_review(q_app, tmp_path):
    folder = tmp_path / "dataset"
    folder.mkdir()
    image = folder / "a.png"
    image.write_bytes(b"x")

    tab = LoRATrainTab()
    tab.apply_imported_paths((str(image),))

    assert tab.data_dir_edit.text() == str(folder)
    assert tab._review_panel._order == []


def test_unified_train_handoff_switches_to_lora(q_app, tmp_path):
    from gui.src.tabs.models.train_tab import UnifiedTrainTab

    folder = tmp_path / "dataset"
    folder.mkdir()
    tab = UnifiedTrainTab()
    tab.model_selector.setCurrentIndex(2)
    tab.apply_imported_paths((str(folder),))

    assert tab.model_selector.currentData() == "anything"
    assert tab.anything_tab.data_dir_edit.text() == str(folder)


def test_trigger_token_round_trips_separately_from_instance_prompt(q_app):
    tab = LoRATrainTab()
    tab.prompt_edit.setText("1girl, style of my_char")
    tab.trigger_edit.setText("my_char")
    snapshot = tab.collect()

    assert snapshot["trigger_prompt"] == "1girl, style of my_char"
    assert snapshot["trigger_token"] == "my_char"

    tab.trigger_edit.clear()
    tab.set_config(snapshot)
    assert tab.trigger_edit.text() == "my_char"


def test_search_send_to_train_publishes_ml_training_intents(q_app):
    from gui.src.tabs.database.search_tab._tab_communication import (
        SearchTabCommunicationController,
    )

    hub = EventHub(q_app)
    events: list[object] = []
    hub.subscribe(ImportPathsIntent, events.append)
    hub.subscribe(NavigateIntent, events.append)
    stub = SimpleNamespace(
        tab=QWidget(),
        event_hub=hub,
        selected_files=["/tmp/a.png"],
    )
    stub._get_target_selection = (
        lambda single_path=None: SearchTabCommunicationController._get_target_selection(
            stub, single_path
        )
    )

    with patch("gui.src.tabs.database.search_tab._tab_communication.QMessageBox"):
        SearchTabCommunicationController.send_selection_to_train_tab(stub)

    assert [type(event) for event in events] == [ImportPathsIntent, NavigateIntent]
    assert events[0].module_id == "ml.training"
    assert events[0].paths == ("/tmp/a.png",)
    assert events[1].module_id == "ml.training"


def test_extractor_send_frames_publishes_ml_training_intents(q_app):
    from gui.src.tabs.core.extractor_tab._directory_scanning import (
        ExtractorDirectoryScanningController,
    )
    from PySide6.QtWidgets import QLineEdit

    hub = EventHub(q_app)
    events: list[object] = []
    hub.subscribe(ImportPathsIntent, events.append)
    hub.subscribe(NavigateIntent, events.append)
    stub = SimpleNamespace(
        tab=QWidget(),
        event_hub=hub,
        line_edit_extract_dir=QLineEdit("/tmp/frames"),
    )

    with patch("gui.src.tabs.core.extractor_tab._directory_scanning.QMessageBox"):
        ExtractorDirectoryScanningController.send_frames_to_train(stub)

    assert [type(event) for event in events] == [ImportPathsIntent, NavigateIntent]
    assert events[0].module_id == "ml.training"
    assert events[0].paths == ("/tmp/frames",)


def test_host_import_paths_activates_train_and_applies(q_app, monkeypatch):
    from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost

    applied: list[tuple[str, ...]] = []

    class FakeTrain(QWidget):
        def apply_imported_paths(self, paths: tuple[str, ...]) -> None:
            applied.append(paths)

    def fake_build(self, route_key: str) -> QWidget:
        if route_key == "train":
            tab = FakeTrain()
            self._train_tab = tab
            return tab
        return QWidget()

    monkeypatch.setattr(DeepLearningWorkspaceHost, "_build_page", fake_build)
    hub = EventHub(q_app)
    DeepLearningWorkspaceHost(event_hub=hub)
    hub.publish(
        ImportPathsIntent(origin="test", module_id="ml.training", paths=("/tmp/ds",))
    )
    assert applied == [("/tmp/ds",)]
