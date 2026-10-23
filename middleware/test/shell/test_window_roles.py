"""WindowManager role map (#873): hide-all labels and the cloud.jobs pop-out."""

from __future__ import annotations

import json
from pathlib import Path

from middleware.src.shell.window_roles import (
    hide_on_close_labels,
    popout_ids,
    request_stop_cloud,
    roles_path,
    windows,
)
from middleware.validation.check_tauri_security import check


def test_hide_on_close_is_the_labeled_webview_set() -> None:
    labels = hide_on_close_labels()
    assert labels == ["main", "cloud-jobs"]
    kinds = {entry["id"]: entry["kind"] for entry in windows()}
    assert kinds["tray"] == "tray"
    assert kinds["slideshow"] == "native"


def test_cloud_jobs_is_a_main_popout_with_its_own_capability() -> None:
    assert popout_ids() == ["cloud.jobs"]
    jobs = next(entry for entry in windows() if entry["id"] == "cloud.jobs")
    assert jobs["role"] == "popout"
    assert jobs["panel_of"] == "main"
    assert jobs["label"] == "cloud-jobs"

    cap_path = Path(__file__).resolve().parents[3] / "frontend" / "src-tauri" / "capabilities" / "cloud.jobs.json"
    capability = json.loads(cap_path.read_text(encoding="utf-8"))
    assert capability["windows"] == ["cloud-jobs"]
    assert capability["permissions"] == ["core:default"]
    blob = json.dumps(capability)
    assert "**" not in blob
    assert "allow" not in blob


def test_role_map_is_the_embedded_json() -> None:
    assert roles_path().is_file()


def test_tauri_security_check_accepts_the_new_window() -> None:
    root = Path(__file__).resolve().parents[3]
    assert check(root) == []


def test_stop_cloud_writes_the_supervisor_flag(tmp_path) -> None:
    path = request_stop_cloud(tmp_path)
    assert path.read_text(encoding="utf-8") == "1\n"
    assert path.name == "cloud_jobs.stop"
