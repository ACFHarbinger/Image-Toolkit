#!/usr/bin/env python3
"""Package the Linux Tauri desktop app into release artifacts (.deb)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def get_app_version() -> str:
    sys.path.insert(0, str(ROOT_DIR))
    try:
        from middleware.src._version import __version__

        return __version__
    except Exception:
        return "1.0.0"


def stage_runtime(frontend_dir: Path) -> None:
    stager = frontend_dir / "src-tauri" / "scripts" / "stage_sidecar_runtime.py"
    if not stager.is_file():
        raise FileNotFoundError(f"stager script not found: {stager}")
    subprocess.run([sys.executable, str(stager)], cwd=frontend_dir, check=True)


def build_tauri(out_dir: Path, version: str, *, dry_run: bool = False) -> list[Path]:
    print("==> Packaging Tauri desktop app...")
    frontend_dir = ROOT_DIR / "frontend"
    out_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print("Dry run requested: verifying scripts and config...")
        stager = frontend_dir / "src-tauri" / "scripts" / "stage_sidecar_runtime.py"
        if not stager.is_file():
            raise FileNotFoundError(f"missing stager: {stager}")
        mock_deb = out_dir / f"image-toolkit-tauri_{version}_amd64.deb"
        print(f"Dry run complete. Target artifact: {mock_deb}")
        return [mock_deb]

    stage_runtime(frontend_dir)
    subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)
    subprocess.run(["npm", "run", "tauri:build"], cwd=frontend_dir, check=True)

    bundle_dir = frontend_dir / "src-tauri" / "target" / "release" / "bundle" / "deb"
    artifacts: list[Path] = []
    if bundle_dir.is_dir():
        for deb in bundle_dir.glob("*.deb"):
            dest = out_dir / f"image-toolkit-tauri_{version}_amd64.deb"
            shutil.copy2(deb, dest)
            artifacts.append(dest)
            print(f"✅ Tauri .deb package built: {dest}")

    return artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate without invoking compiler")
    parser.add_argument("--out-dir", type=Path, default=ROOT_DIR / "dist" / "release")
    args = parser.parse_args()

    version = get_app_version()
    build_tauri(args.out_dir, version, dry_run=args.dry_run)
    print("🎉 Tauri packaging step complete.")


if __name__ == "__main__":
    main()
