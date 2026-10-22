"""Pure (Qt-free) serializable shortcut registry loader.

Shared by PySide6 and Tauri shells. Loads contracts/shortcuts/registry.json
and user overrides from ~/.image-toolkit/keybindings.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict


class Action(TypedDict):
    id: str
    description: str
    scope: str
    default: str


class Registry(TypedDict):
    version: int
    actions: List[Action]


def load_registry(path: Optional[Path] = None) -> Registry:
    if path is None:
        # Default relative to repo or installed location; callers should pass explicit path
        path = Path(__file__).parent.parent.parent / "contracts" / "shortcuts" / "registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise ValueError(f"Unsupported registry version: {data.get('version')}")
    return data  # type: ignore[return-value]


def load_overrides(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    if path is None:
        from gui.src.constants.utils import _KEYBINDINGS_PATH  # lazy, only for Python shell
        path = _KEYBINDINGS_PATH
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
    defaults = {a["id"]: a["default"] for a in registry["actions"]}
    st = overrides.get(action_id, {"default_enabled": True, "custom": []})
    keys: List[str] = []
    if st.get("default_enabled", True):
        default = defaults.get(action_id, "")
        if default:
            keys.append(default)
    keys.extend(k for k in st.get("custom", []) if k)
    return keys
