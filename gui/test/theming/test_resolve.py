from gui.src.theming.resolve import (
    base_defaults,
    derive_accent_variants,
    resolve_colors,
    resolve_to_qss_vars,
    to_qss_vars,
)
from gui.src.theming.schema import ThemePack


class TestBaseDefaults:
    def test_dark_matches_theme_qss_defaults(self):
        # gui/src/styles/qss/theme.qss's @vars block, dark section.
        dark = base_defaults("dark")
        assert dark.accent == "#00bcd4"
        assert dark.surface == "#2d2d30"
        assert dark.window_bg == "#1e1e1e"
        assert dark.text == "#cccccc"
        assert dark.muted_text == "#888888"
        assert dark.border == "#3e3e3e"

    def test_light_matches_theme_qss_defaults(self):
        light = base_defaults("light")
        assert light.accent == "#007AFF"
        assert light.window_bg == "#f5f5f5"
        assert light.surface == "#ffffff"


class TestResolveColors:
    def test_no_overrides_equals_base_defaults(self):
        pack = ThemePack(name="x", base="dark")
        assert resolve_colors(pack) == base_defaults("dark")

    def test_sparse_override_only_changes_that_token(self):
        pack = ThemePack(name="x", base="dark", color_overrides={"accent": "#ff00ff"})
        resolved = resolve_colors(pack)
        assert resolved.accent == "#ff00ff"
        assert resolved.window_bg == base_defaults("dark").window_bg  # untouched

    def test_switching_base_reresolves_unset_tokens(self):
        # Same override, different base -- override persists, everything
        # else re-derives from the new base (the whole point of the
        # base+delta model: a follow-system toggle doesn't lose overrides).
        pack_dark = ThemePack(name="x", base="dark", color_overrides={"accent": "#ff00ff"})
        pack_light = ThemePack(name="x", base="light", color_overrides={"accent": "#ff00ff"})
        assert resolve_colors(pack_dark).accent == "#ff00ff"
        assert resolve_colors(pack_light).accent == "#ff00ff"
        assert resolve_colors(pack_dark).window_bg != resolve_colors(pack_light).window_bg


class TestDeriveAccentVariants:
    def test_matches_compute_accent_vars_darker_math(self):
        # gui/src/styles/__init__.py::compute_accent_vars uses
        # QColor(accent).darker(115)/.darker(132) for hover/pressed.
        # This module's QColor-free math must agree.
        from PySide6.QtGui import QColor

        accent = "#00bcd4"
        variants = derive_accent_variants(accent)
        expected_hover = QColor(accent).darker(115).name()
        expected_pressed = QColor(accent).darker(132).name()
        assert variants["accent_hover"] == expected_hover
        assert variants["accent_pressed"] == expected_pressed


class TestToQssVars:
    def test_maps_onto_existing_var_names(self):
        resolved = base_defaults("dark")
        qss_vars = to_qss_vars(resolved, prefix="DARK")
        assert qss_vars["DARK_ACCENT_COLOR"] == resolved.accent
        assert qss_vars["DARK_BG"] == resolved.window_bg
        assert qss_vars["DARK_SECONDARY_BG"] == resolved.surface
        assert qss_vars["DARK_TEXT"] == resolved.text
        assert qss_vars["DARK_MUTED_TEXT"] == resolved.muted_text
        assert qss_vars["DARK_BORDER"] == resolved.border
        assert "DARK_ACCENT_HOVER" in qss_vars
        assert "DARK_ACCENT_PRESSED" in qss_vars
        assert "DARK_ACCENT_MUTED" in qss_vars

    def test_resolve_to_qss_vars_uses_pack_base_as_prefix(self):
        pack = ThemePack(name="x", base="light")
        qss_vars = resolve_to_qss_vars(pack)
        assert "LIGHT_ACCENT_COLOR" in qss_vars
        assert qss_vars["LIGHT_ACCENT_COLOR"] == base_defaults("light").accent

    def test_round_trips_through_real_load_qss_with_overrides(self):
        # The actual hybrid bridge: generated vars must be consumable by
        # the existing QSS loader unmodified.
        from gui.src.styles import load_qss_with_overrides

        pack = ThemePack(name="x", base="dark", color_overrides={"accent": "#ff00ff"})
        qss_vars = resolve_to_qss_vars(pack)
        qss = load_qss_with_overrides("dark.qss", qss_vars)
        assert "#ff00ff" in qss.lower()
