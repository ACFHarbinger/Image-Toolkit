"""Regression: build_application_catalog()'s factories must actually
construct real tab widgets with real constructors, not just fake/counting
factories the way test_lazy_runtime_contract.py and test_runtime.py do.

Codex's authorized D12 live-desktop smoke (`47595fdf`) found a real
cross-branch API incompatibility: #536's catalog was built against
#533's runtime alone (`feature/ui-arch-13-runtime-shell`, never rebased
onto #534), so its `_create_search_tab` factory called `SearchTab`'s
NEW (database_service, event_hub, dropdown) constructor while that
branch still had the OLD (db_tab_ref, dropdown) signature -- a
TypeError on the very first cross-category navigation
(system.convert -> library.search), reproducing the "authorized live
desktop smoke failed" state exactly. Confirmed this does not reproduce
on `main` after the wave-2 merge combined #534+#536 -- #534's SearchTab
migration and #536's catalog landed together -- but nothing in the test
suite actually exercised the real factories end-to-end before this, so
add it as permanent coverage against the next time these two evolve on
separate branches again.
"""

import pytest
from gui.src.modules.application_catalog import build_application_catalog
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.events import EventHub
from gui.src.modules.runtime import ModuleRuntime
from gui.src.preferences import PreferenceStore

pytestmark = pytest.mark.gui


@pytest.fixture
def runtime(q_app):
    PreferenceStore.reset_instance()
    store = PreferenceStore.instance()
    catalog = build_application_catalog(dropdown=True, enable_manager=False, preference_store=store)
    ctx = ModuleContext(event_hub=EventHub(q_app), services=ModuleServices(), preference_store=store)
    return ModuleRuntime(catalog, ctx)


@pytest.mark.parametrize(
    "module_id,expected_type",
    [
        ("system.convert", "ConvertTab"),
        ("library.search", "SearchTab"),
        ("library.scan", "ScanMetadataTab"),
        ("system.wallpaper", "WallpaperTab"),
        ("library.management", "DatabaseTab"),
        ("library.listings", "ListingsTab"),
    ],
)
def test_activate_each_database_family_route(runtime, module_id, expected_type):
    handle = runtime.handle_for(module_id)
    assert type(handle.widget).__name__ == expected_type


def test_cross_category_navigation_sequence(runtime):
    """Mirrors Codex's D12 smoke: start on Convert (first activation), then
    navigate to library.search (cross-category) without a constructor error.
    """
    convert_handle = runtime.handle_for("system.convert")
    assert type(convert_handle.widget).__name__ == "ConvertTab"

    search_handle = runtime.handle_for("library.search")
    assert type(search_handle.widget).__name__ == "SearchTab"

    # both stay independently created, no duplicate/second host
    assert runtime.is_created("system.convert")
    assert runtime.is_created("library.search")
