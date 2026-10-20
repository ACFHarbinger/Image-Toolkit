"""WindowManager role map for the Tauri shell (W0-09 / #873).

Ids match the catalog window set (main, tray, slideshow, cloud.jobs).
This file is the native-label map the Rust registry embeds; #869/#870
must not grow a second list of window ids.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROLES_REL = Path("frontend/src-tauri/windows/roles.json")
CLOUD_STOP_NAME = "cloud_jobs.stop"


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


def hide_on_close_labels(root: str | None = None) -> list[str]:
    """Labels ``collect_background_windows`` would hide with ``main``."""
    labels: list[str] = []
    for entry in windows(root):
        if entry.get("kind") != "webview" or not entry.get("hide_on_close"):
            continue
        label = entry.get("id")
        if isinstance(label, str):
            labels.append(label)
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
