"""Production catalog coverage for the MainWindow runtime-shell experiment (#515)."""

import sys
import types

import pytest
from gui.src.modules.application_catalog import build_application_catalog
from gui.src.modules.catalog import ModuleKind
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.events import EventHub
from gui.src.modules.library_service import LIBRARY_DATABASE_SERVICE, LibraryDatabaseService
from gui.src.modules.runtime import ModuleRuntime
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture
def q_app():
    return QApplication.instance() or QApplication([])


def test_application_catalog_has_every_legacy_route_without_constructing_widgets():
    catalog = build_application_catalog(dropdown=True, enable_manager=False)
    descriptors = catalog.all_descriptors()

    assert len([item for item in descriptors if item.kind != ModuleKind.WORKSPACE]) == 33
    assert catalog.require("system.convert").title == "Convert"
    assert catalog.require("library.management").title == "Management"
    assert catalog.require("stitch.canvas").title == "Canvas"
    assert catalog.require("editor.hybrid").title == "Hybrid Editor"
    assert len(catalog.navigable_by_category(catalog.require("stitch").category)) == 8


def test_application_catalog_constructs_a_page_only_when_activated(q_app, monkeypatch):
    constructions: list[dict] = []

    class FakeConvertTab(QWidget):
        def __init__(self, **kwargs) -> None:
            super().__init__()
            constructions.append(kwargs)

    fake_tabs = types.ModuleType("gui.src.tabs")
    fake_tabs.ConvertTab = FakeConvertTab
    monkeypatch.setitem(sys.modules, "gui.src.tabs", fake_tabs)
    import gui.src

    monkeypatch.setattr(gui.src, "tabs", fake_tabs, raising=False)
    catalog = build_application_catalog(dropdown=False, enable_manager=False)
    services = ModuleServices()
    services.register("vault_manager", object())
    services.register(LIBRARY_DATABASE_SERVICE, LibraryDatabaseService(None))
    runtime = ModuleRuntime(catalog, ModuleContext(EventHub(q_app), services))

    assert constructions == []
    first = runtime.activate("system.convert")
    second = runtime.activate("system.convert")

    assert first is second
    assert constructions == [{"dropdown": False}]


def test_every_production_route_has_a_constructible_factory(q_app, monkeypatch):
    constructions: list[str] = []

    def fake_tab(name: str):
        class FakeTab(QWidget):
            def __init__(self, *args, **kwargs) -> None:
                super().__init__()
                constructions.append(name)

        return FakeTab

    fake_tabs = types.ModuleType("gui.src.tabs")
    for name in (
        "ComfyUITab", "ConvertTab", "DatabaseTab", "DataBrowserTab", "DriveSyncTab",
        "EntityReconTab", "ExtractorTab", "HieEditorTab", "ImageCrawlTab", "ListingsTab",
        "MangaAnimationTab", "MangaColorizationTab", "MangaPuppeteeringTab", "MediaLoaderTab",
        "MergeTab", "MetaCLIPInferenceTab", "R3GANEvaluateTab", "ReverseImageSearchTab",
        "ScanMetadataTab", "SearchTab", "SimilarityTab", "UnifiedGenerateTab", "UnifiedTrainTab",
        "WallpaperTab", "WebRequestsTab",
    ):
        setattr(fake_tabs, name, fake_tab(name))
    monkeypatch.setitem(sys.modules, "gui.src.tabs", fake_tabs)
    import gui.src

    monkeypatch.setattr(gui.src, "tabs", fake_tabs, raising=False)

    class FakeStitchTab(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self._tab_widget = types.SimpleNamespace(setCurrentIndex=lambda _index: None)
            constructions.append("StitchTab")

    monkeypatch.setitem(sys.modules, "asp_gui", types.ModuleType("asp_gui"))
    asp_elements = types.ModuleType("asp_gui.elements")
    asp_elements.StitchTab = FakeStitchTab
    monkeypatch.setitem(sys.modules, "asp_gui.elements", asp_elements)

    catalog = build_application_catalog(dropdown=False, enable_manager=False)
    services = ModuleServices()
    services.register("vault_manager", object())
    services.register(LIBRARY_DATABASE_SERVICE, LibraryDatabaseService(None))
    runtime = ModuleRuntime(catalog, ModuleContext(EventHub(q_app), services))

    for descriptor in catalog.all_descriptors():
        if descriptor.kind != ModuleKind.WORKSPACE:
            runtime.activate(descriptor.module_id)

    assert len(constructions) == 26
    assert constructions.count("StitchTab") == 1
