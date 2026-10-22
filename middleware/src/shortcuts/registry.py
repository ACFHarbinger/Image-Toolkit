"""Pure (Qt-free) serializable shortcut registry loader.

Shared by PySide6 and Tauri shells. Loads contracts/shortcuts/registry.json
and user overrides from ~/.image-toolkit/keybindings.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, NotRequired, Optional, TypedDict


class Action(TypedDict):
    id: str
    description: str
    scope: str
    default: str
    also: NotRequired[List[str]]


class Registry(TypedDict):
    version: int
    actions: List[Action]


def default_registry_path() -> Path:
    """Repo-root contract, or the copy PyInstaller places under ``_MEIPASS``."""
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        bundled = Path(bundled_root) / "contracts" / "shortcuts" / "registry.json"
        if bundled.is_file():
            return bundled
    # registry.py lives in middleware/src/shortcuts/, so the repo root is four parents up.
    return Path(__file__).resolve().parents[3] / "contracts" / "shortcuts" / "registry.json"


def _default_chords(action: Action) -> List[str]:
    """The default chord plus aliases that turn off with it."""
    chords: List[str] = []
    default = action.get("default") or ""
    if default:
        chords.append(default)
    chords.extend(key for key in action.get("also") or [] if key)
    return chords


def load_registry(path: Optional[Path] = None) -> Registry:
    if path is None:
        path = default_registry_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"Unsupported registry version: {data.get('version')}")
    return data  # type: ignore[return-value]


def keybindings_path() -> Path:
    """Same file the Qt shell writes, resolved without importing PySide6."""
    return Path.home() / ".image-toolkit" / "keybindings.json"


def load_overrides(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    if path is None:
        path = keybindings_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    # Normalize legacy string overrides
    normalized: Dict[str, Dict[str, Any]] = {}
    for action_id, value in raw.items():
        if isinstance(value, str):
            normalized[action_id] = {"default_enabled": False, "custom": [value] if value else []}
        elif isinstance(value, dict):
            normalized[action_id] = {
                "default_enabled": bool(value.get("default_enabled", True)),
                "custom": [k for k in value.get("custom", []) if k],
            }
    return normalized


def active_keys(registry: Registry, overrides: Dict[str, Dict[str, Any]], action_id: str) -> List[str]:
    actions = {a["id"]: a for a in registry["actions"]}
    st = overrides.get(action_id, {"default_enabled": True, "custom": []})
    keys: List[str] = []
    if st.get("default_enabled", True) and action_id in actions:
        keys.extend(_default_chords(actions[action_id]))
    keys.extend(k for k in st.get("custom", []) if k)
    return keys
