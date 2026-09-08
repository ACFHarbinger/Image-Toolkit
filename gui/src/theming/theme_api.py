"""Runtime theme token helpers for components (#564).

Bridges semantic color tokens and component QSS fragments onto the existing
``THEME_VARS`` / ``resolve_colors`` machinery — no duplicate token tables.
"""

from __future__ import annotations

import os
from string import Template
from typing import Any

from gui.src.styles import THEME_VARS
from gui.src.theming.resolve import base_defaults, derive_accent_variants

_COMPONENTS_DIR = os.path.join(os.path.dirname(__file__), "qss", "components")

_TOKEN_SUFFIX: dict[str, str] = {
    "accent": "ACCENT_COLOR",
    "accent_hover": "ACCENT_HOVER",
    "accent_pressed": "ACCENT_PRESSED",
    "surface": "SECONDARY_BG",
    "window_bg": "BG",
    "text": "TEXT",
    "muted_text": "MUTED_TEXT",
    "border": "BORDER",
    "success": "SUCCESS",
    "danger": "DANGER",
}


def color(token: str, *, base: str = "dark") -> str:
    """Semantic token → ``#rrggbb``.

    Tokens: accent, accent_hover, accent_pressed, surface, window_bg, text,
    muted_text, border, success, danger.
    """
    if base not in ("dark", "light"):
        raise ValueError(f"base must be 'dark' or 'light', got {base!r}")
    if token not in _TOKEN_SUFFIX:
        raise KeyError(f"Unknown color token {token!r}; expected one of {sorted(_TOKEN_SUFFIX)}")
    prefix = base.upper()
    key = f"{prefix}_{_TOKEN_SUFFIX[token]}"
    if key in THEME_VARS:
        return THEME_VARS[key]
    resolved = base_defaults(base)
    variants = derive_accent_variants(resolved.accent)
    fallback = {
        "accent": resolved.accent,
        "accent_hover": variants["accent_hover"],
        "accent_pressed": variants["accent_pressed"],
        "surface": resolved.surface,
        "window_bg": resolved.window_bg,
        "text": resolved.text,
        "muted_text": resolved.muted_text,
        "border": resolved.border,
        "success": "#2e7d32",
        "danger": "#c62828",
    }
    return fallback[token]


def accent_rgba(alpha: float = 0.2, *, base: str = "dark") -> str:
    """Theme accent as ``rgba(r, g, b, alpha)`` for QSS backgrounds."""
    hex_color = color("accent", base=base).lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def qss(component: str, *, base: str = "dark", **vars: Any) -> str:
    """Load ``gui/src/theming/qss/components/{component}.qss`` with ``$VAR`` substitution."""
    path = os.path.join(_COMPONENTS_DIR, f"{component}.qss")
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Component QSS not found: {component!r}") from exc

    merged = dict(THEME_VARS)
    prefix = base.upper()
    for token, suffix in _TOKEN_SUFFIX.items():
        merged[f"{prefix}_{suffix}"] = color(token, base=base)
    merged.update(vars)
    return Template(content).safe_substitute(merged)


def apply_stylesheet(widget, stylesheet: str) -> None:
    """Apply a pre-built application stylesheet (e.g. from ``load_qss_with_overrides``)."""
    widget.setStyleSheet(stylesheet)


__all__ = ["accent_rgba", "apply_stylesheet", "color", "qss"]
