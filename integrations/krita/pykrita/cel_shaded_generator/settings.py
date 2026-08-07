"""Atomic XDG settings shared by the installer and constrained Krita host."""

from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_SCHEMA_VERSION = 1
SHORTCUT_ACTIONS = ("review", "accept", "reject")


def default_config_path():
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "cel-shaded-generator" / "krita.json"


def load_config(path=None):
    target = Path(path) if path is not None else default_config_path()
    if not target.exists():
        return {"schema_version": CONFIG_SCHEMA_VERSION, "shortcuts": _empty_shortcuts()}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("Krita tutor configuration is invalid JSON") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != CONFIG_SCHEMA_VERSION:
        raise ValueError("Krita tutor configuration schema is unsupported")
    shortcuts = payload.get("shortcuts", {})
    if not isinstance(shortcuts, dict):
        raise ValueError("Krita tutor shortcuts must be an object")
    payload["shortcuts"] = _validate_shortcuts(shortcuts)
    return payload


def save_shortcuts(shortcuts, path=None):
    target = Path(path) if path is not None else default_config_path()
    payload = load_config(target)
    payload["shortcuts"] = _validate_shortcuts(shortcuts)
    _atomic_write(target, payload)
    return target


def merge_engine_executable(executable, path=None):
    target = Path(path) if path is not None else default_config_path()
    payload = load_config(target)
    payload["engine_executable"] = str(executable)
    _atomic_write(target, payload)
    return target


def _validate_shortcuts(shortcuts):
    normalized = {}
    for action in SHORTCUT_ACTIONS:
        value = shortcuts.get(action, "")
        if not isinstance(value, str):
            raise ValueError("Krita tutor shortcuts must be strings")
        normalized[action] = value.strip()
    assigned = [value.casefold() for value in normalized.values() if value]
    if len(assigned) != len(set(assigned)):
        raise ValueError("Krita tutor shortcuts must be unique")
    return normalized


def _empty_shortcuts():
    return {action: "" for action in SHORTCUT_ACTIONS}


def _atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
