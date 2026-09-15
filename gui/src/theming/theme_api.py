"""Runtime theme token helpers for components (#564, #620).

Bridges semantic color tokens and component QSS fragments onto the existing
``THEME_VARS`` / ``resolve_colors`` machinery — no duplicate token tables.

``qss()`` returns a ``ThemedQss`` string that records the component name and
extra substitutions. Applying it via ``QWidget.setStyleSheet`` registers the
widget so ``refresh_component_styles()`` can re-substitute against the live
base after a theme toggle (#620).
"""

from __future__ import annotations

import logging
import os
import weakref
from string import Template
from typing import Any

from gui.src.styles import THEME_VARS
from gui.src.theming.resolve import base_defaults, derive_accent_variants

logger = logging.getLogger(__name__)

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

_current_base: str = "dark"
_TRACKER_INSTALLED = False
_BINDINGS: weakref.WeakKeyDictionary[Any, tuple[str, dict[str, Any]]] = weakref.WeakKeyDictionary()


class ThemedQss(str):
    """Stylesheet text that still knows which component QSS produced it."""

    component: str
    extra: dict[str, Any]

    def __new__(cls, text: str, component: str, extra: dict[str, Any]):
        obj = str.__new__(cls, text)
        obj.component = component
        obj.extra = extra
        return obj


def current_base() -> str:
    """Base theme last installed by ``set_current_base`` / a refresh."""
    return _current_base


def set_current_base(base: str) -> None:
    """Record the live dark/light base used when ``qss()``/``color()`` omit ``base``."""
    if base not in ("dark", "light"):
        raise ValueError(f"base must be 'dark' or 'light', got {base!r}")
    global _current_base
    _current_base = base


def _resolve_base(base: str | None) -> str:
    if base is None:
        return _current_base
    if base not in ("dark", "light"):
        raise ValueError(f"base must be 'dark' or 'light', got {base!r}")
    return base


def color(token: str, *, base: str | None = None) -> str:
    """Semantic token → ``#rrggbb``.

    Tokens: accent, accent_hover, accent_pressed, surface, window_bg, text,
    muted_text, border, success, danger. ``base`` defaults to the live theme.
    """
    resolved = _resolve_base(base)
    if token not in _TOKEN_SUFFIX:
        raise KeyError(f"Unknown color token {token!r}; expected one of {sorted(_TOKEN_SUFFIX)}")
    prefix = resolved.upper()
    key = f"{prefix}_{_TOKEN_SUFFIX[token]}"
    if key in THEME_VARS:
        return THEME_VARS[key]
    defaults = base_defaults(resolved)
    variants = derive_accent_variants(defaults.accent)
    fallback = {
        "accent": defaults.accent,
        "accent_hover": variants["accent_hover"],
        "accent_pressed": variants["accent_pressed"],
        "surface": defaults.surface,
        "window_bg": defaults.window_bg,
        "text": defaults.text,
        "muted_text": defaults.muted_text,
        "border": defaults.border,
        "success": "#2e7d32",
        "danger": "#c62828",
    }
    return fallback[token]


def accent_rgba(alpha: float = 0.2, *, base: str | None = None) -> str:
    """Theme accent as ``rgba(r, g, b, alpha)`` for QSS backgrounds."""
    hex_color = color("accent", base=base).lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


class ThemeColor:
    """A ``qss(**vars)`` extra that re-resolves against the live base.

    ``refresh_component_styles()`` reuses a widget's original ``**vars``
    verbatim on every toggle (#620) -- a plain literal like
    ``ACCENT=color("accent")`` freezes at construction time and never
    changes, which is why most of the app stayed the old theme after a
    toggle while only the header (restyled explicitly, not through this
    generic path) actually updated. Pass ``ThemeColor("accent")`` instead
    of the literal and it re-resolves via ``color()``/``accent_rgba()``
    every time ``qss()`` substitutes it, construction or refresh alike.
    """

    __slots__ = ("token", "alpha")

    def __init__(self, token: str, *, alpha: float | None = None) -> None:
        self.token = token
        self.alpha = alpha

    def resolve(self, base: str) -> str:
        if self.alpha is not None:
            return accent_rgba(self.alpha, base=base)
        return color(self.token, base=base)


def _ensure_stylesheet_tracker() -> None:
    """Record ``ThemedQss`` applications so a later refresh can re-substitute."""
    global _TRACKER_INSTALLED
    if _TRACKER_INSTALLED:
        return
    from PySide6.QtWidgets import QWidget

    original = QWidget.setStyleSheet

    def tracked(self, sheet) -> None:  # noqa: ANN001
        if isinstance(sheet, ThemedQss):
            _BINDINGS[self] = (sheet.component, dict(sheet.extra))
            original(self, str(sheet))
            return
        _BINDINGS.pop(self, None)
        original(self, sheet)

    QWidget.setStyleSheet = tracked  # type: ignore[method-assign]
    _TRACKER_INSTALLED = True


def _widget_is_alive(widget: Any) -> bool:
    try:
        from shiboken6 import isValid

        return bool(isValid(widget))
    except Exception:
        try:
            widget.objectName()
        except RuntimeError:
            return False
        return True


def qss(component: str, *, base: str | None = None, **vars: Any) -> ThemedQss:
    """Load ``gui/src/theming/qss/components/{component}.qss`` with ``$VAR`` substitution."""
    _ensure_stylesheet_tracker()
    resolved = _resolve_base(base)
    path = os.path.join(_COMPONENTS_DIR, f"{component}.qss")
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Component QSS not found: {component!r}") from exc

    merged = dict(THEME_VARS)
    # Fragments were authored against $DARK_* names. Remap both prefixes
    # onto the live base so a refresh actually changes colors (#620).
    src_prefix = resolved.upper()
    for key in THEME_VARS:
        if key.startswith("DARK_") or key.startswith("LIGHT_"):
            suffix = key.split("_", 1)[1]
            live_key = f"{src_prefix}_{suffix}"
            if live_key in THEME_VARS:
                merged[key] = THEME_VARS[live_key]
    for token, suffix in _TOKEN_SUFFIX.items():
        value = color(token, base=resolved)
        merged[f"DARK_{suffix}"] = value
        merged[f"LIGHT_{suffix}"] = value
    resolved_vars = {k: (v.resolve(resolved) if isinstance(v, ThemeColor) else v) for k, v in vars.items()}
    merged.update(resolved_vars)
    return ThemedQss(Template(content).safe_substitute(merged), component, dict(vars))


def apply_qss(widget, component: str, *, base: str | None = None, **vars: Any) -> None:
    """Apply a named component fragment and register it for live refresh."""
    widget.setStyleSheet(qss(component, base=base, **vars))


def refresh_component_styles(*, base: str | None = None) -> int:
    """Re-apply every tracked ``qss()`` stylesheet against ``base``.

    Returns the number of live widgets restyled. Extra ``**vars`` captured
    at the original ``setStyleSheet(qss(...))`` call are reused as-is except
    for ``ThemeColor`` markers, which re-resolve against ``base`` here; call
    sites that pass a plain literal for a theme-dependent color (rather than
    ``ThemeColor``) will not follow a later toggle -- same as the header
    restyling itself explicitly after this walk.
    """
    resolved = _resolve_base(base)
    set_current_base(resolved)
    _ensure_stylesheet_tracker()
    applied = 0
    dead: list[Any] = []
    for widget, (component, extra) in list(_BINDINGS.items()):
        if not _widget_is_alive(widget):
            dead.append(widget)
            continue
        widget.setStyleSheet(qss(component, base=resolved, **extra))
        # setStyleSheet() alone does not reliably trigger a repaint with the
        # new colors on an already-rendered widget (#620): Qt's style-sheet
        # cache for that widget needs an explicit unpolish/polish cycle to
        # actually recompute, and a repaint needs an explicit update() since
        # the style change alone doesn't always schedule one. Best-effort:
        # some widget subclasses override update()/style-related methods
        # with an incompatible signature, so a failure here must never
        # break the refresh for the rest of the tree.
        try:
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
            widget.update()
        except Exception:
            logger.debug("Suppressed Exception in refresh_component_styles repaint", exc_info=True)
        applied += 1
    for widget in dead:
        _BINDINGS.pop(widget, None)
    return applied


def apply_stylesheet(widget, stylesheet: str) -> None:
    """Apply a pre-built application stylesheet (e.g. from ``load_qss_with_overrides``).

    Clears the existing sheet before setting the new one (#620): on an
    already-built, already-polished widget tree, calling ``setStyleSheet()``
    a second time with different content does not reliably force Qt to
    re-cascade style-sheet-derived properties on descendants that matched a
    type selector in the *previous* sheet but have no local override of
    their own -- only widgets with an explicit per-widget stylesheet (e.g.
    the header, restyled directly in ``_theme.py``) reliably repaint. An
    explicit clear-then-set forces Qt to tear down and rebuild the whole
    style-sheet-applied state instead of diffing against the prior content.
    """
    widget.setStyleSheet("")
    widget.setStyleSheet(stylesheet)


__all__ = [
    "ThemeColor",
    "ThemedQss",
    "accent_rgba",
    "apply_qss",
    "apply_stylesheet",
    "color",
    "current_base",
    "qss",
    "refresh_component_styles",
    "set_current_base",
]
