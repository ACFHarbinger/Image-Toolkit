"""WindowManager role map for the Tauri shell (W0-09 / #873).

Ids match the catalog window set (main, tray, slideshow, cloud.jobs).
This file is the native-label map the Rust registry embeds; #869/#870
must not grow a second list of window ids. A native label is the optional
``label`` field, otherwise the id. Tauri accepts only alphanumeric
characters, ``-``, ``/``, ``:`` and ``_`` — the cloud.jobs role uses
``cloud-jobs``.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

ROLES_REL = Path("frontend/src-tauri/windows/roles.json")
CLOUD_STOP_NAME = "cloud_jobs.stop"
# Tauri's runtime label grammar. Dots are rejected at startup.
_NATIVE_LABEL = re.compile(r"^[A-Za-z0-9/:_-]+$")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def roles_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / ROLES_REL


@lru_cache(maxsize=1)
def load_roles(root: str | None = None) -> dict[str, Any]:
    path = roles_path(Path(root) if root else None)
    return json.loads(path.read_text(encoding="utf-8"))


def windows(root: str | None = None) -> list[dict[str, Any]]:
    payload = load_roles(root)
    entries = payload.get("windows", [])
    if not isinstance(entries, list):
        raise ValueError(f"{ROLES_REL}: 'windows' must be a list")
    return entries


def native_label(entry: dict[str, Any]) -> str:
    """Tauri window label for a role. Logical ids may contain dots."""
    raw = entry.get("label", entry.get("id"))
    if not isinstance(raw, str) or _NATIVE_LABEL.fullmatch(raw) is None:
        raise ValueError(f"invalid native window label {raw!r}")
    return raw


def hide_on_close_labels(root: str | None = None) -> list[str]:
    """Native labels hidden with ``main`` (not the dotted catalog ids)."""
    labels: list[str] = []
    for entry in windows(root):
        if entry.get("kind") != "webview" or not entry.get("hide_on_close"):
            continue
        labels.append(native_label(entry))
    return labels


def popout_ids(root: str | None = None) -> list[str]:
    return [
        entry["id"] for entry in windows(root) if entry.get("role") == "popout" and isinstance(entry.get("id"), str)
    ]


def request_stop_cloud(data_dir: Path) -> Path:
    """Ask the cloud_jobs sibling to stop in-flight work. Daemons stay up."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / CLOUD_STOP_NAME
    path.write_text("1\n", encoding="utf-8")
    return path
