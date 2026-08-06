#!/usr/bin/env python3
"""Install/uninstall the plugin without touching unrelated Krita plugins."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

PLUGIN_NAME = "cel_shaded_generator"


def default_root() -> Path:
    """Return the Krita Snap user plugin directory."""
    return Path.home() / "snap" / "krita" / "current" / ".local" / "share" / "krita" / "pykrita"


def install(root: Path) -> None:
    """Install this plugin, refusing to overwrite an unknown existing package."""
    source = Path(__file__).parent / "pykrita"
    package = root / PLUGIN_NAME
    desktop = root / f"{PLUGIN_NAME}.desktop"
    if package.exists() or desktop.exists():
        raise FileExistsError("plugin already exists; uninstall it explicitly before reinstalling")
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source / PLUGIN_NAME, package)
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
    args = parser.parse_args()
    (install if args.action == "install" else uninstall)(args.root)


if __name__ == "__main__":
    main()
