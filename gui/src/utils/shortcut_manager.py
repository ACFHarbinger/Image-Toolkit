"""
Central keyboard shortcut registry (GUI/UX §2.29).

All app shortcuts are registered here with an id, description, scope, and
default key sequence.  Runtime overrides are loaded from
~/.image-toolkit/keybindings.json on first use and written back on save.

Usage
-----
    from gui.src.utils.shortcut_manager import get_registry

    reg = get_registry()

    # In keyPressEvent:
    if reg.matches(event, "gallery.select_all"):
        ...

    # For QShortcut construction:
    shortcut = QShortcut(reg.get_key_sequence("preview.zoom_in"), parent)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QKeyEvent, QKeySequence


# ---------------------------------------------------------------------------
# Registry definition — one entry per bindable action
# ---------------------------------------------------------------------------
SHORTCUT_REGISTRY: list[dict] = [
    # Gallery — two-gallery base class
    {
        "id": "gallery.select_all",
        "description": "Select all images on current page",
        "scope": "Gallery",
        "default": "Ctrl+A",
    },
    {
        "id": "gallery.deselect_all",
        "description": "Deselect all images",
        "scope": "Gallery",
        "default": "Ctrl+D",
    },
    {
        "id": "gallery.nav_left",
        "description": "Move gallery focus left",
        "scope": "Gallery",
        "default": "Left",
    },
    {
        "id": "gallery.nav_right",
        "description": "Move gallery focus right",
        "scope": "Gallery",
        "default": "Right",
    },
    {
        "id": "gallery.nav_up",
        "description": "Move gallery focus up",
        "scope": "Gallery",
        "default": "Up",
    },
    {
        "id": "gallery.nav_down",
        "description": "Move gallery focus down",
        "scope": "Gallery",
        "default": "Down",
    },
    {
        "id": "gallery.open_preview",
        "description": "Open preview for focused image (Space also works)",
        "scope": "Gallery",
        "default": "Return",
    },
    {
        "id": "gallery.export_paths",
        "description": "Export selection as paths list (TXT/CSV)",
        "scope": "Gallery",
        "default": "Ctrl+E",
    },
    {
        "id": "gallery.rename",
        "description": "Rename the focused / selected image (F2)",
        "scope": "Gallery",
        "default": "F2",
    },
    {
        "id": "gallery.copy_to_folder",
        "description": "Copy selection to a chosen folder",
        "scope": "Gallery",
        "default": "Ctrl+Shift+C",
    },
    {
        "id": "gallery.nav_back",
        "description": "Navigate to previous directory (Alt+Left)",
        "scope": "Gallery",
        "default": "Alt+Left",
    },
    {
        "id": "gallery.nav_forward",
        "description": "Navigate to next directory (Alt+Right)",
        "scope": "Gallery",
        "default": "Alt+Right",
    },
    # Image Preview window
    {
        "id": "preview.zoom_in",
        "description": "Zoom in (also Ctrl+Shift++)",
        "scope": "Preview",
        "default": "Ctrl+=",
    },
    {
        "id": "preview.zoom_out",
        "description": "Zoom out",
        "scope": "Preview",
        "default": "Ctrl+-",
    },
    {
        "id": "preview.next",
        "description": "Next image",
        "scope": "Preview",
        "default": "Right",
    },
    {
        "id": "preview.prev",
        "description": "Previous image",
        "scope": "Preview",
        "default": "Left",
    },
    {
        "id": "preview.close",
        "description": "Close preview window",
        "scope": "Preview",
        "default": "Ctrl+W",
    },
    {
        "id": "preview.copy",
        "description": "Copy image to clipboard",
        "scope": "Preview",
        "default": "Ctrl+C",
    },
    {
        "id": "preview.fullscreen",
        "description": "Toggle fullscreen (F also works)",
        "scope": "Preview",
        "default": "F11",
    },
    {
        "id": "preview.fit_width",
        "description": "Fit image to window width",
        "scope": "Preview",
        "default": "W",
    },
    {
        "id": "preview.fit_height",
        "description": "Fit image to window height",
        "scope": "Preview",
        "default": "H",
    },
    {
        "id": "preview.actual_size",
        "description": "Show image at 100% zoom",
        "scope": "Preview",
        "default": "1",
    },
    {
        "id": "preview.rotate_cw",
        "description": "Rotate image 90° clockwise",
        "scope": "Preview",
        "default": "R",
    },
    {
        "id": "preview.rotate_ccw",
        "description": "Rotate image 90° counter-clockwise",
        "scope": "Preview",
        "default": "L",
    },
]

_KEYBINDINGS_PATH = Path.home() / ".image-toolkit" / "keybindings.json"


class ShortcutRegistry:
    def __init__(self) -> None:
        self._defaults: dict[str, str] = {
            e["id"]: e["default"] for e in SHORTCUT_REGISTRY
        }
        self._overrides: dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if _KEYBINDINGS_PATH.exists():
            try:
                self._overrides = json.loads(_KEYBINDINGS_PATH.read_text())
            except Exception:
                self._overrides = {}

    def save(self, overrides: dict[str, str]) -> None:
        """Persist user overrides to ~/.image-toolkit/keybindings.json."""
        _KEYBINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _KEYBINDINGS_PATH.write_text(json.dumps(overrides, indent=2))
        self._overrides = overrides

    def reset(self) -> None:
        """Clear all overrides and delete the JSON file."""
        self._overrides = {}
        if _KEYBINDINGS_PATH.exists():
            _KEYBINDINGS_PATH.unlink()

    # ------------------------------------------------------------------
    def get_key(self, action_id: str) -> str:
        """Return the active key string for an action (override > default)."""
        return self._overrides.get(action_id, self._defaults.get(action_id, ""))

    def get_key_sequence(self, action_id: str) -> QKeySequence:
        return QKeySequence(self.get_key(action_id))

    def matches(self, event: QKeyEvent, action_id: str) -> bool:
        """Return True if *event* matches the binding for *action_id*.

        Works across PySide6 versions where event.key() may return int or
        Qt.Key enum, and event.modifiers() returns a KeyboardModifier flag.
        """
        key_str = self.get_key(action_id)
        if not key_str:
            return False
        seq = QKeySequence(key_str)
        if seq.isEmpty():
            return False
        raw_key = event.key()
        raw_mods = event.modifiers()
        key_int: int = (
            raw_key
            if isinstance(raw_key, int)
            else (raw_key.value if hasattr(raw_key, "value") else int(raw_key))
        )
        mods_int: int = raw_mods.value if hasattr(raw_mods, "value") else int(raw_mods)
        event_seq = QKeySequence(mods_int | key_int)
        return seq == event_seq

    def get_all(self) -> list[dict]:
        """Return registry entries annotated with the current active binding."""
        return [
            {**entry, "current": self._overrides.get(entry["id"], entry["default"])}
            for entry in SHORTCUT_REGISTRY
        ]

    def get_overrides(self) -> dict[str, str]:
        return dict(self._overrides)

    def is_default(self, action_id: str) -> bool:
        return action_id not in self._overrides


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_registry: Optional[ShortcutRegistry] = None


def get_registry() -> ShortcutRegistry:
    global _registry
    if _registry is None:
        _registry = ShortcutRegistry()
    return _registry
