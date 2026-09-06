"""Tests for per-category accent overrides and bilingual navigation (§2.37, §2.41, #518, #541)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.components.navigation.navigation_rail import NavigationRailWidget
from gui.src.components.navigation.segmented_ribbon import TopSegmentedRibbonWidget
from gui.src.components.navigation.shell_manager import ShellLayoutManager, ShellNavMode
from gui.src.modules.catalog import ModuleCatalog, PageDescriptor
from gui.src.modules.context import ModuleContext, ModuleServices
from gui.src.modules.descriptor import ModuleCategory
from gui.src.modules.events import EventHub
from gui.src.modules.runtime import ModuleRuntime
from gui.src.preferences import PreferenceStore
from gui.src.preferences.definitions import PrefKeys
from gui.src.theming.resolve import resolve_category_accent
from gui.src.theming.schema import ThemePack, ThemeSchemaError

pytestmark = pytest.mark.gui


def test_theme_pack_category_accent_validation():
    # Valid category overrides
    pack = ThemePack(
        name="CyberpunkCategory",
        base="dark",
        category_accent_overrides={
            "system": "#ff0055",
            "manga": "#00ffcc",
        },
    )
    assert pack.category_accent_overrides["system"] == "#ff0055"
    assert pack.category_accent_overrides["manga"] == "#00ffcc"

    # Invalid hex color in category override should fail
    with pytest.raises(ThemeSchemaError):
        ThemePack(
            name="BadColor",
            category_accent_overrides={"system": "not-a-color"},
        )


def test_resolve_category_accent():
    pack = ThemePack(
        name="AnimeStudio",
        base="dark",
        color_overrides={"accent": "#00bcd4"},
        category_accent_overrides={
            "deep_learning": "#9c27b0",
            "editor": "#e91e63",
        },
    )

    # Overridden category
    assert resolve_category_accent(pack, "deep_learning") == "#9c27b0"
    assert resolve_category_accent(pack, ModuleCategory.DEEP_LEARNING) == "#9c27b0"
    assert resolve_category_accent(pack, "editor") == "#e91e63"

    # Fallback category inherits global accent
    assert resolve_category_accent(pack, "system") == "#00bcd4"
    assert resolve_category_accent(pack, ModuleCategory.SYSTEM) == "#00bcd4"


def test_navigation_category_accents_ui(q_app):
    catalog = ModuleCatalog()
    catalog.register(
        PageDescriptor(
            module_id="sys.test",
            title="System Test",
            category=ModuleCategory.SYSTEM,
            factory=lambda ctx: None,
        )
    )
    catalog.register(
        PageDescriptor(
            module_id="manga.test",
            title="Manga Test",
            category=ModuleCategory.MANGA,
            factory=lambda ctx: None,
        )
    )

    rail = NavigationRailWidget(catalog)
    rail.apply_category_accents({"system": "#ff0055", "manga": "#00ffcc"})
    assert rail._category_accent_overrides["system"] == "#ff0055"

    # Check header styling and bilingual text
    rail.select_category(ModuleCategory.SYSTEM)
    assert "#ff0055" in rail.drawer_header.styleSheet()
    assert "システム" in rail.drawer_header.text()

    rail.select_category(ModuleCategory.MANGA)
    assert "#00ffcc" in rail.drawer_header.styleSheet()
    assert "マンガ" in rail.drawer_header.text()

    ribbon = TopSegmentedRibbonWidget(catalog)
    ribbon.apply_category_accents({"system": "#ff0055", "manga": "#00ffcc"})
    assert ribbon._category_accent_overrides["system"] == "#ff0055"


def test_shell_manager_category_accents_and_prefs(q_app, tmp_path, monkeypatch):
    store = PreferenceStore()
    store.set(PrefKeys.CATEGORY_ACCENTS, {"system": "#e0245e", "library": "#17bf63"})

    catalog = ModuleCatalog()
    catalog.register(
        PageDescriptor(
            module_id="sys.test",
            title="System Test",
            category=ModuleCategory.SYSTEM,
            factory=lambda ctx: QWidget(),
        )
    )
    services = ModuleServices()
    context = ModuleContext(
        event_hub=EventHub(q_app),
        services=services,
        preference_store=store,
    )
    runtime = ModuleRuntime(catalog, context)

    container = QWidget()
    manager = ShellLayoutManager(runtime, container, default_mode=ShellNavMode.RAIL)

    # Trigger deferred initial accents timer
    manager._apply_initial_category_accents()

    assert manager.rail._category_accent_overrides.get("system") == "#e0245e"
    assert manager.ribbon._category_accent_overrides.get("library") == "#17bf63"

    # Dynamically apply new accents
    manager.apply_category_accents({"system": "#00f0ff"})
    assert manager.rail._category_accent_overrides.get("system") == "#00f0ff"
    assert manager.ribbon._category_accent_overrides.get("system") == "#00f0ff"

    manager.clear_mounted()
    runtime.dispose()


def test_shell_manager_accents_apply_through_real_deferred_timer(q_app):
    """The existing test above calls _apply_initial_category_accents()
    directly, which never actually exercises the deferred QTimer path
    (#540's "no blocking work during construction" lesson) -- verify the
    real event-loop-driven behavior: not applied synchronously in
    __init__, applied after one event-loop turn, and cancelable if
    clear_mounted() runs before that turn.
    """
    from PySide6.QtCore import QCoreApplication

    store = PreferenceStore()
    store.set(PrefKeys.CATEGORY_ACCENTS, {"system": "#e0245e"})

    catalog = ModuleCatalog()
    catalog.register(
        PageDescriptor(
            module_id="sys.test",
            title="System Test",
            category=ModuleCategory.SYSTEM,
            factory=lambda ctx: QWidget(),
        )
    )
    context = ModuleContext(
        event_hub=EventHub(q_app), services=ModuleServices(), preference_store=store
    )
    runtime = ModuleRuntime(catalog, context)
    container = QWidget()

    # Positive path: applies naturally after one event-loop turn.
    manager = ShellLayoutManager(runtime, container, default_mode=ShellNavMode.RAIL)
    assert not getattr(manager.rail, "_category_accent_overrides", {})
    QCoreApplication.processEvents()
    assert manager.rail._category_accent_overrides.get("system") == "#e0245e"
    manager.clear_mounted()
    runtime.dispose()

    # Cancellation path: disposing before the deferred turn runs must
    # prevent it from firing at all.
    runtime2 = ModuleRuntime(catalog, context)
    container2 = QWidget()
    manager2 = ShellLayoutManager(runtime2, container2, default_mode=ShellNavMode.RAIL)
    manager2.clear_mounted()
    QCoreApplication.processEvents()
    assert not getattr(manager2.rail, "_category_accent_overrides", {})
    runtime2.dispose()
