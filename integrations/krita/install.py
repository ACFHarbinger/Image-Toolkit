#!/usr/bin/env python3
"""Install/uninstall the plugin without touching unrelated Krita plugins."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

PLUGIN_NAME = "cel_shaded_generator"


def default_root() -> Path:
    """Return the standard Linux/AppImage Krita user plugin directory."""
    return Path.home() / ".local" / "share" / "krita" / "pykrita"


def default_config_path() -> Path:
    """Return the plugin's XDG-compatible host configuration path."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_home / "cel-shaded-generator" / "krita.json"


def configure_engine(engine: Path, config_path: Path | None = None) -> Path:
    """Atomically record one explicit engine executable without shell arguments."""
    resolved = engine.expanduser().resolve()
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ValueError("engine must be an existing executable file")
    target = config_path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(
        json.dumps({"schema_version": 1, "engine_executable": str(resolved)}, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def install(root: Path) -> None:
    """Install this plugin, refusing to overwrite an unknown existing package."""
    if "snap/krita" in root.as_posix():
        raise RuntimeError(
            "the Krita Snap build omits Python plugin support; use the official AppImage"
        )
    source = Path(__file__).parent / "pykrita"
    package = root / PLUGIN_NAME
    desktop = root / f"{PLUGIN_NAME}.desktop"
    if package.exists() or desktop.exists():
        raise FileExistsError("plugin already exists; uninstall it explicitly before reinstalling")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source / PLUGIN_NAME,
        package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    shutil.copy2(source / f"{PLUGIN_NAME}.desktop", desktop)


def uninstall(root: Path) -> None:
    """Remove only files with this plugin's exact names."""
    package = root / PLUGIN_NAME
    desktop = root / f"{PLUGIN_NAME}.desktop"
    if package.is_dir():
        shutil.rmtree(package)
    desktop.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--root", type=Path, default=default_root())
    parser.add_argument("--engine", type=Path)
    args = parser.parse_args()
    (install if args.action == "install" else uninstall)(args.root)
    if args.action == "install" and args.engine is not None:
        configure_engine(args.engine)


if __name__ == "__main__":
    main()
