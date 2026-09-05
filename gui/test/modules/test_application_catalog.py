"""Production catalog coverage for the MainWindow runtime-shell experiment (#515)."""

from gui.src.modules.application_catalog import build_application_catalog
from gui.src.modules.catalog import ModuleKind


def test_application_catalog_has_every_legacy_route_without_constructing_widgets():
    catalog = build_application_catalog(dropdown=True, enable_manager=False)
    descriptors = catalog.all_descriptors()

    assert len([item for item in descriptors if item.kind != ModuleKind.WORKSPACE]) == 33
    assert catalog.require("system.convert").title == "Convert"
    assert catalog.require("library.management").title == "Management"
    assert catalog.require("stitch.canvas").title == "Canvas"
    assert catalog.require("editor.hybrid").title == "Hybrid Editor"
