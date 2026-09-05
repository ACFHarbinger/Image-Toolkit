import pytest
from gui.src.modules.catalog import ModuleCatalog, PageDescriptor
from gui.src.modules.descriptor import ModuleCategory
from gui.src.theming.resolve import resolve_category_accent, resolve_colors
from gui.src.theming.schema import ThemePack, ThemeSchemaError
from gui.src.components.navigation.navigation_rail import NavigationRailWidget
from gui.src.components.navigation.segmented_ribbon import TopSegmentedRibbonWidget


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


def test_navigation_category_accents_ui():
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

    ribbon = TopSegmentedRibbonWidget(catalog)
    ribbon.apply_category_accents({"system": "#ff0055", "manga": "#00ffcc"})
    assert ribbon._category_accent_overrides["system"] == "#ff0055"
