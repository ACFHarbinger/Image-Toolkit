"""
Central keyboard shortcut registry (GUI/UX §2.29).

All app shortcuts are registered here with an id, description, scope, and
default key sequence.  Runtime overrides are loaded from
~/.image-toolkit/keybindings.json on first use and written back on save.

The static registry is now loaded from the shared serializable source
(contracts/shortcuts/registry.json) so both shells bind the same data.
Global OS shortcuts are limited to tray show/hide.

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
from middleware.src.shortcuts.registry import load_registry

# ---------------------------------------------------------------------------
# Registry definition — loaded from the shared serializable source
# ---------------------------------------------------------------------------
_SHARED = load_registry()
SHORTCUT_REGISTRY: list[dict] = _SHARED["actions"]


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
