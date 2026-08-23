"""
Central keyboard shortcut registry (GUI/UX §2.29).

All app shortcuts are registered here with an id, description, scope, and
default key sequence.  Runtime overrides are loaded from
~/.image-toolkit/keybindings.json on first use and written back on save.

Each action supports, independently:
  - toggling its default binding on/off (``default_enabled``)
  - any number of additional custom bindings (``custom``)
mirroring how KDE's System Settings > Shortcuts editor lets a single
action ("Launch Dolphin") keep its default (Meta+E) while also carrying
several user-added custom bindings side by side.

Usage
-----
    from gui.src.utils import get_registry

    reg = get_registry()

    # In keyPressEvent:
    if reg.matches(event, "gallery.select_all"):
        ...

    # For QShortcut construction (single QKeySequence: default if enabled,
    # else the first custom binding):
    shortcut = QShortcut(reg.get_key_sequence("preview.zoom_in"), parent)
"""

from __future__ import annotations

import json
from typing import Optional

from PySide6.QtGui import QKeyEvent, QKeySequence

from gui.src.constants.utils import _KEYBINDINGS_PATH

# ---------------------------------------------------------------------------
# Registry definition — one entry per bindable action
# ---------------------------------------------------------------------------
SHORTCUT_REGISTRY: list[dict] = [
    # General — app-wide actions, not scoped to a single widget
    {
        "id": "general.save_tab_config",
        "description": "Save current tab's configuration as a named profile",
        "scope": "General",
        "default": "Ctrl+S",
    },
    {
        "id": "general.load_tab_config",
        "description": "Load a saved configuration into the current tab",
        "scope": "General",
        "default": "Meta+S",
    },
    {
        "id": "general.global_search",
        "description": "Search for a file across every loaded gallery tab",
        "scope": "General",
        "default": "Ctrl+Shift+F",
    },
    {
        "id": "general.workflow_templates",
        "description": "Open the workflow templates picker (run/create a cross-tab setup)",
        "scope": "General",
        "default": "Ctrl+Shift+M",
    },
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
    {
        "id": "gallery.compare_selected",
        "description": "Compare selected images side-by-side (C)",
        "scope": "Gallery",
        "default": "C",
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


class ShortcutRegistry:
    def __init__(self) -> None:
        self._defaults: dict[str, str] = {
            e["id"]: e["default"] for e in SHORTCUT_REGISTRY
        }
        # action_id -> {"default_enabled": bool, "custom": [key_str, ...]}
        self._state: dict[str, dict] = {}
        self._load()

    # ------------------------------------------------------------------
    def _load(self) -> None:
        if not _KEYBINDINGS_PATH.exists():
            return
        try:
            raw = json.loads(_KEYBINDINGS_PATH.read_text())
        except Exception:
            return
        if not isinstance(raw, dict):
            return
        for action_id, value in raw.items():
            if isinstance(value, str):
                # Pre-§2.16-multi-shortcut format: a single override string
                # fully replaced the default. Preserve that meaning: default
                # off, the old override becomes the one custom binding.
                self._state[action_id] = {
                    "default_enabled": False,
                    "custom": [value] if value else [],
                }
            elif isinstance(value, dict):
                self._state[action_id] = {
                    "default_enabled": bool(value.get("default_enabled", True)),
                    "custom": [k for k in value.get("custom", []) if k],
                }

    def save(self, state: dict[str, dict]) -> None:
        """Persist the full per-action state to ~/.image-toolkit/keybindings.json.

        *state* maps action_id -> {"default_enabled": bool, "custom": [str, ...]}.
        """
        _KEYBINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _KEYBINDINGS_PATH.write_text(json.dumps(state, indent=2))
        self._state = state

    def reset(self) -> None:
        """Clear all overrides and delete the JSON file."""
        self._state = {}
        if _KEYBINDINGS_PATH.exists():
            _KEYBINDINGS_PATH.unlink()

    # ------------------------------------------------------------------
    def _entry_state(self, action_id: str) -> dict:
        return self._state.get(action_id, {"default_enabled": True, "custom": []})

    def is_default_enabled(self, action_id: str) -> bool:
        return bool(self._entry_state(action_id).get("default_enabled", True))

    def get_custom_keys(self, action_id: str) -> list[str]:
        return list(self._entry_state(action_id).get("custom", []))

    def get_all_keys(self, action_id: str) -> list[str]:
        """Every currently active key string for *action_id* (default, if
        enabled, followed by every custom binding)."""
        st = self._entry_state(action_id)
        keys: list[str] = []
        if st.get("default_enabled", True):
            default = self._defaults.get(action_id, "")
            if default:
                keys.append(default)
        keys.extend(k for k in st.get("custom", []) if k)
        return keys

    def get_key(self, action_id: str) -> str:
        """The single "primary" active key string for an action -- the
        default (if enabled), else the first custom binding, else "".
        Used where only one QKeySequence can be constructed (e.g. a single
        QShortcut); prefer get_all_keys()/matches() where multiple
        simultaneous bindings should all work."""
        keys = self.get_all_keys(action_id)
        return keys[0] if keys else ""

    def get_key_sequence(self, action_id: str) -> QKeySequence:
        return QKeySequence(self.get_key(action_id))

    def matches(self, event: QKeyEvent, action_id: str) -> bool:
        """Return True if *event* matches ANY active binding (default, if
        enabled, or any custom binding) for *action_id*.

        Works across PySide6 versions where event.key() may return int or
        Qt.Key enum, and event.modifiers() returns a KeyboardModifier flag.
        """
        raw_key = event.key()
        raw_mods = event.modifiers()
        key_int: int = (
            raw_key
            if isinstance(raw_key, int)
            else (raw_key.value if hasattr(raw_key, "value") else int(raw_key))
        )
        mods_int: int = raw_mods.value if hasattr(raw_mods, "value") else int(raw_mods) # pyrefly: ignore [bad-argument-type]
        event_seq = QKeySequence(mods_int | key_int)

        for key_str in self.get_all_keys(action_id):
            seq = QKeySequence(key_str)
            if not seq.isEmpty() and seq == event_seq:
                return True
        return False

    def get_all(self) -> list[dict]:
        """Return registry entries annotated with the current active binding(s).

        ``current`` is a human-readable, comma-joined summary of every
        active key (default + customs) for display/search purposes (e.g.
        the Ctrl+/ shortcut-discovery overlay).
        """
        return [
            {**entry, "current": ", ".join(self.get_all_keys(entry["id"])) or "(none)"}
            for entry in SHORTCUT_REGISTRY
        ]

    def get_overrides(self) -> dict[str, dict]:
        return dict(self._state)

    def is_default(self, action_id: str) -> bool:
        return action_id not in self._state


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_registry: Optional[ShortcutRegistry] = None


def get_registry() -> ShortcutRegistry:
    global _registry
    if _registry is None:
        _registry = ShortcutRegistry()
    return _registry
