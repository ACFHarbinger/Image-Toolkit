"""Curated theme presets and visual tokens for the Anime Creative Suite (#438, gui_ux.md §2.37).

Provides pre-configured ThemePack presets tailored for anime art, manga drafting,
and creative workflows, plus standardized Danbooru/e621 tag taxonomy palette mappings.
"""

from __future__ import annotations

from .schema import CornerTokens, DensityTokens, ShadowTokens, ThemePack, TypographyTokens

#: Danbooru/e621 standard tag taxonomy colors
DANBOORU_TAG_COLORS: dict[str, dict[str, str]] = {
    "character": {"bg": "rgba(85, 197, 122, 0.18)", "text": "#55c57a", "border": "rgba(85, 197, 122, 0.35)"},
    "copyright": {"bg": "rgba(192, 132, 252, 0.18)", "text": "#c084fc", "border": "rgba(192, 132, 252, 0.35)"},
    "artist": {"bg": "rgba(248, 113, 113, 0.18)", "text": "#f87171", "border": "rgba(248, 113, 113, 0.35)"},
    "general": {"bg": "rgba(56, 189, 248, 0.18)", "text": "#38bdf8", "border": "rgba(56, 189, 248, 0.35)"},
    "meta": {"bg": "rgba(251, 146, 60, 0.18)", "text": "#fb923c", "border": "rgba(251, 146, 60, 0.35)"},
}

#: Built-in theme presets
THEME_PRESETS: dict[str, ThemePack] = {
    "Neo-Tokyo": ThemePack(
        name="Neo-Tokyo",
        base="dark",
        color_overrides={
            "accent": "#00f0ff",
            "surface": "#161822",
            "window_bg": "#0e0f14",
            "text": "#e2e8f0",
            "muted_text": "#71717a",
            "border": "#27273a",
        },
        corners=CornerTokens(radius_px=4),
        shadows=ShadowTokens(blur_radius_px=8),
        typography=TypographyTokens(font_family="Segoe UI", scale_percent=100),
    ),
    "Sakura Blossom": ThemePack(
        name="Sakura Blossom",
        base="dark",
        color_overrides={
            "accent": "#ff70a6",
            "surface": "#1c1926",
            "window_bg": "#121118",
            "text": "#f3e8ee",
            "muted_text": "#8b8599",
            "border": "#2e293d",
        },
        corners=CornerTokens(radius_px=8),
        shadows=ShadowTokens(blur_radius_px=6),
        typography=TypographyTokens(font_family="Segoe UI", scale_percent=100),
    ),
    "Evangelion 01": ThemePack(
        name="Evangelion 01",
        base="dark",
        color_overrides={
            "accent": "#9b5de5",
            "surface": "#181b28",
            "window_bg": "#0f111a",
            "text": "#00f5d4",
            "muted_text": "#7b829e",
            "border": "#2c2847",
        },
        corners=CornerTokens(radius_px=4),
        shadows=ShadowTokens(blur_radius_px=10),
        typography=TypographyTokens(font_family="Segoe UI", scale_percent=100),
    ),
    "Catppuccin Mocha": ThemePack(
        name="Catppuccin Mocha",
        base="dark",
        color_overrides={
            "accent": "#89b4fa",
            "surface": "#25253a",
            "window_bg": "#1e1e2e",
            "text": "#cdd6f4",
            "muted_text": "#a6adc8",
            "border": "#313244",
        },
        corners=CornerTokens(radius_px=8),
        shadows=ShadowTokens(blur_radius_px=8),
        typography=TypographyTokens(font_family="Segoe UI", scale_percent=100),
    ),
    "Manga Ink": ThemePack(
        name="Manga Ink",
        base="dark",
        color_overrides={
            "accent": "#f8fafc",
            "surface": "#1e1e1e",
            "window_bg": "#121212",
            "text": "#ffffff",
            "muted_text": "#94a3b8",
            "border": "#333333",
        },
        corners=CornerTokens(radius_px=0),
        shadows=ShadowTokens(blur_radius_px=0),
        typography=TypographyTokens(font_family="Segoe UI", scale_percent=100),
    ),
    "Solarized Anime": ThemePack(
        name="Solarized Anime",
        base="dark",
        color_overrides={
            "accent": "#ffb703",
            "surface": "#073642",
            "window_bg": "#002b36",
            "text": "#93a1a1",
            "muted_text": "#586e75",
            "border": "#0e4b58",
        },
        corners=CornerTokens(radius_px=4),
        shadows=ShadowTokens(blur_radius_px=4),
        typography=TypographyTokens(font_family="Segoe UI", scale_percent=100),
    ),
    "Catppuccin Latte": ThemePack(
        name="Catppuccin Latte",
        base="light",
        color_overrides={
            "accent": "#1e66f5",
            "surface": "#e6e9ef",
            "window_bg": "#eff1f5",
            "text": "#4c4f69",
            "muted_text": "#7c7f93",
            "border": "#ccd0da",
        },
        corners=CornerTokens(radius_px=8),
        shadows=ShadowTokens(blur_radius_px=4),
        typography=TypographyTokens(font_family="Segoe UI", scale_percent=100),
    ),
    "Paper Modern": ThemePack(
        name="Paper Modern",
        base="light",
        color_overrides={
            "accent": "#0284c7",
            "surface": "#ffffff",
            "window_bg": "#f8fafc",
            "text": "#0f172a",
            "muted_text": "#64748b",
            "border": "#e2e8f0",
        },
        corners=CornerTokens(radius_px=4),
        shadows=ShadowTokens(blur_radius_px=2),
        typography=TypographyTokens(font_family="Segoe UI", scale_percent=100),
    ),
}


def get_preset(name: str) -> ThemePack | None:
    """Retrieve a theme preset by name, or None if not found."""
    return THEME_PRESETS.get(name)


def list_presets() -> list[str]:
    """List all available preset names."""
    return list(THEME_PRESETS.keys())


__all__ = ["DANBOORU_TAG_COLORS", "THEME_PRESETS", "get_preset", "list_presets"]
