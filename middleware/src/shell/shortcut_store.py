"""Pure (Qt-free) shortcut store for the serializable registry (#872).

Shared by the PySide6 ShortcutRegistry and the Tauri shell.
Loads contracts/shortcuts/registry.json + user ~/.image-toolkit/keybindings.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict


class Action(TypedDict):
    id: str
    description: str
    scope: str
    default: str


class Override(TypedDict):
    default_enabled: bool
    custom: list[str]


class ShortcutStore:
    """Qt-free loader for the shared shortcut registry and user overrides."""

    def __init__(self, registry_path: Path, keybindings_path: Path) -> None:
        self._registry_path = registry_path
        self._keybindings_path = keybindings_path
        self._actions: dict[str, Action] = {}
        self._overrides: dict[str, Override] = {}
        self.reload()

    def reload(self) -> None:
        raw = json.loads(self._registry_path.read_text(encoding="utf-8"))
        if raw.get("version") != 1:
            raise ValueError(f"unsupported registry version: {raw.get('version')}")
        self._actions = {a["id"]: a for a in raw["actions"]}

        self._overrides = {}
        if not self._keybindings_path.exists():
            return
        try:
            user = json.loads(self._keybindings_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(user, dict):
            return
        for aid, val in user.items():
            if isinstance(val, str):
                # backward-compat: old flat string fully replaced the default
                self._overrides[aid] = {
                    "default_enabled": False,
                    "custom": [val] if val else [],
                }
            elif isinstance(val, dict):
                self._overrides[aid] = {
                    "default_enabled": bool(val.get("default_enabled", True)),
                    "custom": [k for k in val.get("custom", []) if k],
                }

    def get_action(self, action_id: str) -> Action | None:
        return self._actions.get(action_id)

    def active_keys(self, action_id: str) -> list[str]:
        """Return every currently active key string for the action."""
        action = self._actions.get(action_id)
        if not action:
            return []
        ov = self._overrides.get(action_id, {"default_enabled": True, "custom": []})
        keys: list[str] = []
        if ov.get("default_enabled", True) and action["default"]:
            keys.append(action["default"])
        keys.extend(ov.get("custom", []))
        return keys

    def all_actions(self) -> list[Action]:
        return list(self._actions.values())

    def scopes(self) -> list[str]:
        return sorted({a["scope"] for a in self._actions.values()})
