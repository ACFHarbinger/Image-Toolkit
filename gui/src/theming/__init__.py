"""Portable theme-pack schema, resolution, storage, and WCAG advisories
(#437, App Theming & Customization -- docs/moon/roadmaps/app_theming_2026q3.md).

Foundational module: the data model + load/save/validate that #438
(Theme Studio UI), #439 (dynamic palette extraction), #440 (background
canvas), and #441 (QSS editor + export/import) all build on. No Theme
Studio UI, no background rendering, no palette-extraction math lives
here -- see those issues.
"""

from .palette import PaletteExtractionResult, extract_palette
from .resolve import base_defaults, derive_accent_variants, resolve_colors, resolve_to_qss_vars, to_qss_vars
from .schema import (
    COLOR_TOKEN_KEYS,
    SCHEMA,
    SCHEMA_VERSION,
    VALID_BASES,
    VALID_DENSITY_MODES,
    VALID_FIT_MODES,
    VALID_ROTATION_INTERVALS_SEC,
    BackgroundAssetRef,
    BackgroundTokens,
    ColorTokens,
    CornerTokens,
    DensityTokens,
    MotionTokens,
    ShadowTokens,
    ThemePack,
    ThemeSchemaError,
    TypographyTokens,
)
from .storage import (
    THEME_ASSETS_DIR,
    THEME_DIR,
    THEME_PACKS_DIR,
    import_asset,
    list_saved_theme_packs,
    load_theme_pack,
    missing_assets,
    resolve_asset_path,
    save_theme_pack,
    theme_pack_from_dict,
    theme_pack_to_dict,
)
from .validate import WCAG_AA_LARGE_TEXT, WCAG_AA_NORMAL_TEXT, ContrastWarning, contrast_ratio, contrast_warnings

__all__ = [
    # schema
    "SCHEMA",
    "SCHEMA_VERSION",
    "VALID_BASES",
    "COLOR_TOKEN_KEYS",
    "VALID_FIT_MODES",
    "VALID_DENSITY_MODES",
    "VALID_ROTATION_INTERVALS_SEC",
    "ThemeSchemaError",
    "ColorTokens",
    "TypographyTokens",
    "CornerTokens",
    "ShadowTokens",
    "MotionTokens",
    "DensityTokens",
    "BackgroundAssetRef",
    "BackgroundTokens",
    "ThemePack",
    # resolve
    "base_defaults",
    "resolve_colors",
    "derive_accent_variants",
    "to_qss_vars",
    "resolve_to_qss_vars",
    # storage
    "THEME_DIR",
    "THEME_PACKS_DIR",
    "THEME_ASSETS_DIR",
    "theme_pack_to_dict",
    "theme_pack_from_dict",
    "save_theme_pack",
    "load_theme_pack",
    "list_saved_theme_packs",
    "import_asset",
    "resolve_asset_path",
    "missing_assets",
    # validate
    "WCAG_AA_NORMAL_TEXT",
    "WCAG_AA_LARGE_TEXT",
    "ContrastWarning",
    "contrast_ratio",
    "contrast_warnings",
    # palette extraction
    "PaletteExtractionResult",
    "extract_palette",
]
