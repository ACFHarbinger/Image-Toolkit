"""Theme-pack schema, resolution, storage, and runtime token helpers.

Lazily re-exported (issues #530, #564, #573): importing this package must
not pull ``palette`` (numpy/PIL) or ``theme_api`` → ``styles``. Leaf
imports such as ``gui.src.theming.theme_api`` stay cheap; palette
extraction loads only when asked. Guarded by
``backend/validation/check_init_boundaries.py``.
"""

from __future__ import annotations

import importlib

_LAZY_EXPORTS = {
    "SCHEMA": ".schema",
    "SCHEMA_VERSION": ".schema",
    "VALID_BASES": ".schema",
    "COLOR_TOKEN_KEYS": ".schema",
    "VALID_FIT_MODES": ".schema",
    "VALID_DENSITY_MODES": ".schema",
    "VALID_ROTATION_INTERVALS_SEC": ".schema",
    "ThemeSchemaError": ".schema",
    "ColorTokens": ".schema",
    "TypographyTokens": ".schema",
    "CornerTokens": ".schema",
    "ShadowTokens": ".schema",
    "MotionTokens": ".schema",
    "DensityTokens": ".schema",
    "BackgroundAssetRef": ".schema",
    "BackgroundTokens": ".schema",
    "ThemePack": ".schema",
    "base_defaults": ".resolve",
    "resolve_colors": ".resolve",
    "derive_accent_variants": ".resolve",
    "to_qss_vars": ".resolve",
    "resolve_to_qss_vars": ".resolve",
    "THEME_DIR": ".storage",
    "THEME_PACKS_DIR": ".storage",
    "THEME_ASSETS_DIR": ".storage",
    "theme_pack_to_dict": ".storage",
    "theme_pack_from_dict": ".storage",
    "save_theme_pack": ".storage",
    "load_theme_pack": ".storage",
    "list_saved_theme_packs": ".storage",
    "import_asset": ".storage",
    "resolve_asset_path": ".storage",
    "missing_assets": ".storage",
    "WCAG_AA_NORMAL_TEXT": ".validate",
    "WCAG_AA_LARGE_TEXT": ".validate",
    "ContrastWarning": ".validate",
    "contrast_ratio": ".validate",
    "contrast_warnings": ".validate",
    "PaletteExtractionResult": ".palette",
    "extract_palette": ".palette",
    "color": ".theme_api",
    "qss": ".theme_api",
}

__all__ = [
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
    "base_defaults",
    "resolve_colors",
    "derive_accent_variants",
    "to_qss_vars",
    "resolve_to_qss_vars",
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
    "WCAG_AA_NORMAL_TEXT",
    "WCAG_AA_LARGE_TEXT",
    "ContrastWarning",
    "contrast_ratio",
    "contrast_warnings",
    "PaletteExtractionResult",
    "extract_palette",
    "color",
    "qss",
]


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(_LAZY_EXPORTS[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
