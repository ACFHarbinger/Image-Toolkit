"""Resolve a ThemePack (base + sparse overrides) into concrete values, and
bridge those values onto the existing $VAR QSS system (#437).

No PySide6 import here either -- color math (darken/lighten) is plain RGB
arithmetic, not QColor, so this stays usable outside a QApplication (and
outside Python, conceptually, once another surface wants to port the
logic). ``gui/src/styles/__init__.py::compute_accent_vars`` already does
the same darken math via QColor for the currently-shipped accent-color
override feature; this module's ``derive_accent_variants`` is the
QColor-free equivalent so the new schema doesn't reintroduce a Qt
dependency the roadmap explicitly wants to avoid. The two are expected to
agree numerically (see test_resolve.py) -- this doesn't replace
``compute_accent_vars``, it's the path new theme-pack code uses.
"""

from __future__ import annotations

from typing import Optional

from .schema import COLOR_TOKEN_KEYS, ColorTokens, ThemePack

#: Base-theme default color tokens, sourced from the same values already
#: shipped in gui/src/styles/qss/theme.qss's @vars block (parsed at import
#: time by gui/src/styles/__init__.py) -- kept as a local literal copy
#: rather than importing gui.src.styles here, since that module has
#: PySide6 imports (QColor, QGraphicsDropShadowEffect) this package
#: deliberately avoids. If theme.qss's defaults ever change, update both
#: (test_resolve.py's parity test will fail loudly if they drift).
_BASE_DEFAULTS: dict[str, dict[str, str]] = {
    "dark": {
        "accent": "#00bcd4",
        "surface": "#2d2d30",
        "window_bg": "#1e1e1e",
        "text": "#cccccc",
        "muted_text": "#888888",
        "border": "#3e3e3e",
    },
    "light": {
        "accent": "#007AFF",
        "surface": "#ffffff",
        "window_bg": "#f5f5f5",
        "text": "#1e1e1e",
        "muted_text": "#555555",
        "border": "#cccccc",
    },
}


def base_defaults(base: str) -> ColorTokens:
    """The unmodified default ColorTokens for a base theme (no overrides)."""
    return ColorTokens(**_BASE_DEFAULTS[base])


def resolve_colors(pack: ThemePack) -> ColorTokens:
    """Base defaults with ``pack.color_overrides`` applied on top.

    This is the base+override-delta model from the locked roadmap: a pack
    stores only what changed, and resolution re-applies those deltas onto
    whichever base is currently selected -- so switching base (e.g. a
    follow-system toggle) re-derives the unset tokens from the new base
    while the user's explicit overrides keep applying.
    """
    values = dict(_BASE_DEFAULTS[pack.base])
    values.update(pack.color_overrides)
    return ColorTokens(**values)


def _scale_hex(hex_color: str, percent: int) -> str:
    """Scale each RGB channel by percent/100, clamped to [0, 255].
    percent > 100 lightens, percent < 100 darkens -- same convention as
    QColor.lighter()/darker() (which take the inverse for darker: this
    function always takes 'how much of the original value to keep').
    """
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    scale = percent / 100.0
    r = max(0, min(255, round(r * scale)))
    g = max(0, min(255, round(g * scale)))
    b = max(0, min(255, round(b * scale)))
    return f"#{r:02x}{g:02x}{b:02x}"


def derive_accent_variants(accent_hex: str) -> dict[str, str]:
    """hover/pressed/muted variants of an accent color.

    hover/pressed match compute_accent_vars's QColor.darker(115)/darker(132)
    (QColor.darker(factor) keeps 100/factor of the original value, i.e. a
    *larger* factor is *darker* -- inverted from this module's _scale_hex
    convention, hence the 10000/factor below). muted has no equivalent in
    the current accent-color-override feature (DARK_ACCENT_MUTED is a
    hardcoded default equal to the border color, not derived from accent
    at all) -- kept that way here: callers needing a muted-accent QSS var
    should use the resolved border color, not this function.
    """
    return {
        "accent_hover": _scale_hex(accent_hex, 10000 / 115),
        "accent_pressed": _scale_hex(accent_hex, 10000 / 132),
    }


def to_qss_vars(resolved: ColorTokens, *, prefix: str) -> dict[str, str]:
    """Map resolved tokens onto the existing $VAR names in
    gui/src/styles/qss/theme.qss (DARK_ACCENT_COLOR, LIGHT_BG, ...) -- the
    hybrid-migration bridge: the new schema generates values the *existing*
    QSS $VAR substitution (gui.src.styles.load_qss_with_overrides) already
    knows how to consume, so dark.qss/light.qss/theme.qss keep working
    unmodified while new code produces their input.

    ``prefix`` is "DARK" or "LIGHT" (matches theme.qss's own var-name
    convention, not schema.VALID_BASES's lowercase "dark"/"light" --
    callers pass ``pack.base.upper()``).
    """
    variants = derive_accent_variants(resolved.accent)
    return {
        f"{prefix}_ACCENT_COLOR": resolved.accent,
        f"{prefix}_ACCENT_HOVER": variants["accent_hover"],
        f"{prefix}_ACCENT_PRESSED": variants["accent_pressed"],
        f"{prefix}_ACCENT_MUTED": resolved.border,
        f"{prefix}_BG": resolved.window_bg,
        f"{prefix}_SECONDARY_BG": resolved.surface,
        f"{prefix}_TEXT": resolved.text,
        f"{prefix}_MUTED_TEXT": resolved.muted_text,
        f"{prefix}_BORDER": resolved.border,
    }


def resolve_to_qss_vars(pack: ThemePack) -> dict[str, str]:
    """Convenience: resolve_colors + to_qss_vars in one call, using
    ``pack.base`` for the $VAR prefix."""
    return to_qss_vars(resolve_colors(pack), prefix=pack.base.upper())


__all__ = [
    "base_defaults",
    "resolve_colors",
    "derive_accent_variants",
    "to_qss_vars",
    "resolve_to_qss_vars",
]
