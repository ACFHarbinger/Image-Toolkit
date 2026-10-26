"""Qt-free settings-window store (#1112).

Profiles, gallery, and logging live in one JSON document. Shortcut overrides
go to the existing keybindings file. Tests pass both paths. Logging values
are stored without opening a log directory.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from middleware.src.bridge.envelope import BridgeAppError
from middleware.src.services.prefs.password import set_master_password
from middleware.src.shortcuts.registry import keybindings_path, load_overrides, load_registry

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

_DEFAULT_PROFILES = {"startup_category": "System Tools", "startup_tab": ""}
_DEFAULT_GALLERY = {
    "thumbnail_size": 180,
    "page_size": 100,
    "confirm_deletions": True,
    "recursive_scan": True,
}
_DEFAULT_LOGGING = {"level": "INFO", "file_logging": False}


def window_prefs_path() -> Path:
    """Default document. Callers that must not touch the home directory pass ``path``."""
    return Path.home() / ".image-toolkit" / "settings" / "window.json"


def _account(account: str) -> str:
    if not isinstance(account, str) or not account.strip():
        raise ValueError("account is required")
    return account.strip()


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


def _text(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


def _flag(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _whole(value: Any, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _require_flag(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _require_whole(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _profiles(raw: Any) -> dict[str, str]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "startup_category": _text(raw.get("startup_category"), _DEFAULT_PROFILES["startup_category"]),
        "startup_tab": _text(raw.get("startup_tab"), _DEFAULT_PROFILES["startup_tab"]),
    }


def _gallery(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "thumbnail_size": _whole(raw.get("thumbnail_size"), _DEFAULT_GALLERY["thumbnail_size"]),
        "page_size": _whole(raw.get("page_size"), _DEFAULT_GALLERY["page_size"]),
        "confirm_deletions": _flag(raw.get("confirm_deletions"), _DEFAULT_GALLERY["confirm_deletions"]),
        "recursive_scan": _flag(raw.get("recursive_scan"), _DEFAULT_GALLERY["recursive_scan"]),
    }


def _logging(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    level = raw.get("level", _DEFAULT_LOGGING["level"])
    if level not in LOG_LEVELS:
        level = _DEFAULT_LOGGING["level"]
    return {
        "level": level,
        "file_logging": _flag(raw.get("file_logging"), _DEFAULT_LOGGING["file_logging"]),
    }


def _checked_profiles(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError("profiles must be an object")
    return {
        "startup_category": _require_text(raw.get("startup_category"), "startup_category"),
        "startup_tab": _require_text(raw.get("startup_tab"), "startup_tab"),
    }


def _checked_gallery(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("gallery must be an object")
    return {
        "thumbnail_size": _require_whole(raw.get("thumbnail_size"), "thumbnail_size"),
        "page_size": _require_whole(raw.get("page_size"), "page_size"),
        "confirm_deletions": _require_flag(raw.get("confirm_deletions"), "confirm_deletions"),
        "recursive_scan": _require_flag(raw.get("recursive_scan"), "recursive_scan"),
    }


def _checked_logging(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("logging must be an object")
    level = raw.get("level")
    if level not in LOG_LEVELS:
        raise ValueError("level must be DEBUG, INFO, WARNING, or ERROR")
    return {
        "level": level,
        "file_logging": _require_flag(raw.get("file_logging"), "file_logging"),
    }


def list_shortcuts(path: Path | None = None) -> list[dict[str, str]]:
    """Registry actions plus the first saved custom chord, if any."""
    overrides = load_overrides(path if path is not None else keybindings_path())
    rows: list[dict[str, str]] = []
    for action in load_registry()["actions"]:
        custom = overrides.get(action["id"], {}).get("custom") or []
        rows.append(
            {
                "id": action["id"],
                "description": action["description"],
                "scope": action["scope"],
                "default": action.get("default") or "",
                "custom": custom[0] if custom else "",
            }
        )
    return rows


def save_override(action: str, chord: str, path: Path | None = None) -> None:
    """Merge one override into the keybindings file. Unknown actions are an error."""
    known = {item["id"] for item in load_registry()["actions"]}
    if action not in known:
        raise BridgeAppError("prefs.unknown_action", details={"action": action})
    target = path if path is not None else keybindings_path()
    current = _read(target)
    previous = current.get(action, {})
    custom = previous.get("custom") or []
    current[action] = {**previous, "custom": [chord, *custom[1:]] if chord else custom[1:]}
    _write(target, current)


def load_window(account: str, *, path: Path | None = None, keybindings: Path | None = None) -> dict[str, Any]:
    cleaned = _account(account)
    stored = _read(path if path is not None else window_prefs_path()).get(cleaned)
    return {
        "account": cleaned,
        "profiles": _profiles(stored.get("profiles") if isinstance(stored, dict) else None),
        "gallery": _gallery(stored.get("gallery") if isinstance(stored, dict) else None),
        "logging": _logging(stored.get("logging") if isinstance(stored, dict) else None),
        "shortcuts": list_shortcuts(keybindings),
    }


def save_window(
    account: str,
    profiles: dict[str, Any],
    gallery: dict[str, Any],
    logging: dict[str, Any],
    *,
    shortcut: dict[str, Any] | None = None,
    current_password: str = "",
    new_password: str = "",
    path: Path | None = None,
    keybindings: Path | None = None,
    session: Any | None = None,
) -> dict[str, Any]:
    """Validate, then persist. An unknown shortcut is rejected before any write."""
    cleaned = _account(account)
    checked_profiles = _checked_profiles(profiles)
    checked_gallery = _checked_gallery(gallery)
    checked_logging = _checked_logging(logging)
    if shortcut is not None:
        action = shortcut.get("action")
        chord = shortcut.get("chord")
        if not isinstance(action, str) or not action or not isinstance(chord, str):
            raise ValueError("shortcut action is required and chord must be a string")
        known = {item["id"] for item in load_registry()["actions"]}
        if action not in known:
            raise BridgeAppError("prefs.unknown_action", details={"action": action})
    else:
        action = ""
        chord = ""

    target = path if path is not None else window_prefs_path()
    document = _read(target)
    document[cleaned] = {
        "profiles": checked_profiles,
        "gallery": checked_gallery,
        "logging": checked_logging,
    }
    _write(target, document)
    if shortcut is not None:
        save_override(action, chord, keybindings)

    password = set_master_password(cleaned, current_password, new_password, session)
    saved = load_window(cleaned, path=target, keybindings=keybindings)
    return {
        "success": password["success"],
        "reason": password["reason"],
        "credentials_changed": password["credentials_changed"],
        **saved,
    }
