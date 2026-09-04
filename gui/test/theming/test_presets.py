"""Tests for Anime Creative Suite presets and Theme Studio integration (§2.37)."""

from __future__ import annotations

import pytest
from gui.src.theming.presets import DANBOORU_TAG_COLORS, THEME_PRESETS, get_preset, list_presets
from gui.src.theming.resolve import resolve_colors
from gui.src.theming.schema import ThemePack

pytestmark = pytest.mark.gui


class TestThemePresets:
    def test_presets_exist_and_validate(self):
        presets = list_presets()
        assert "Neo-Tokyo" in presets
        assert "Sakura Blossom" in presets
        assert "Evangelion 01" in presets
        assert "Catppuccin Mocha" in presets
        assert "Manga Ink" in presets
        assert "Solarized Anime" in presets

        for name in presets:
            pack = get_preset(name)
            assert isinstance(pack, ThemePack)
            resolved = resolve_colors(pack)
            assert resolved.accent.startswith("#")
            assert resolved.surface.startswith("#")
            assert resolved.window_bg.startswith("#")

    def test_danbooru_tag_colors(self):
        for category in ("character", "copyright", "artist", "general", "meta"):
            assert category in DANBOORU_TAG_COLORS
            assert "bg" in DANBOORU_TAG_COLORS[category]
            assert "text" in DANBOORU_TAG_COLORS[category]
            assert "border" in DANBOORU_TAG_COLORS[category]

    def test_theme_studio_preset_selection(self, q_app):
        from gui.src.theming.theme_studio import ThemeStudioPanel

        pack = ThemePack(name="test")
        applied = []
        panel = ThemeStudioPanel(pack, apply_callback=applied.append)

        # Select Neo-Tokyo preset
        panel.preset_combo.setCurrentText("Neo-Tokyo")
        assert applied
        latest = applied[-1]
        assert latest.name == "Neo-Tokyo"
        assert latest.color_overrides.get("accent") == "#00f0ff"
