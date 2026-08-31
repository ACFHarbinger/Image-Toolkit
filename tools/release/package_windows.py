#!/usr/bin/env python3
"""Package the Windows PySide6 desktop app into a zip artifact."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def get_app_version() -> str:
    sys.path.insert(0, str(ROOT_DIR))
    try:
        from backend.src._version import __version__

        return __version__
    except Exception:
        return "0.1.0"


def build_pyinstaller() -> Path:
    dist_dir = ROOT_DIR / "dist" / "ImageToolkit"
    print("==> Running PyInstaller on Windows...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--clean",
            "--noconfirm",
            "ImageToolkit.spec",
        ],
        cwd=ROOT_DIR,
        check=True,
    )
    if not dist_dir.exists():
        raise RuntimeError(f"PyInstaller build failed: {dist_dir} does not exist")
    return dist_dir


def package_zip(dist_dir: Path, out_dir: Path, version: str) -> Path:
    print("==> Creating zip archive...")
    zip_base = out_dir / f"ImageToolkit-{version}-windows-x86_64"
    archive_path = shutil.make_archive(
        str(zip_base),
        "zip",
        root_dir=dist_dir.parent,
        base_dir=dist_dir.name,
    )
    print(f"✅ Windows release archive created: {archive_path}")
    return Path(archive_path)


def main() -> None:
    version = get_app_version()
    out_dir = ROOT_DIR / "dist" / "release"
    out_dir.mkdir(parents=True, exist_ok=True)

    dist_dir = build_pyinstaller()
    package_zip(dist_dir, out_dir, version)
    print(f"🎉 Windows release bundle complete in {out_dir}")


if __name__ == "__main__":
    main()
