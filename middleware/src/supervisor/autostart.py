"""Linux XDG autostart for the supervisor (Wave 0 Linux-first)."""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

DESKTOP_NAME = "image-toolkit-supervisor.desktop"


def autostart_dir(config_home: Path | None = None) -> Path:
    if config_home is None:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "autostart"


def desktop_path(config_home: Path | None = None) -> Path:
    return autostart_dir(config_home) / DESKTOP_NAME


def default_exec_argv(data_dir: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "middleware.src.supervisor",
        "--data-dir",
        str(data_dir),
        "--foreground",
    ]


def enable(
    *,
    data_dir: Path,
    config_home: Path | None = None,
    exec_argv: list[str] | None = None,
) -> Path:
    path = desktop_path(config_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    argv = exec_argv if exec_argv is not None else default_exec_argv(data_dir)
    exec_line = " ".join(shlex.quote(part) for part in argv)
    body = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Image Toolkit Supervisor\n"
        "Comment=Keep the Image Toolkit sidecar and daemons running\n"
        f"Exec={exec_line}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    path.write_text(body, encoding="utf-8")
    os.chmod(path, 0o644)
    return path


def disable(config_home: Path | None = None) -> None:
    path = desktop_path(config_home)
    if path.exists():
        path.unlink()


def is_enabled(config_home: Path | None = None) -> bool:
    return desktop_path(config_home).is_file()
