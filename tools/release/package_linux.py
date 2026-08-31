#!/usr/bin/env python3
"""Package the Linux PySide6 desktop app into AppImage and .deb artifacts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
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
    print("==> Running PyInstaller...")
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


def ensure_appimagetool(cache_dir: Path) -> Path:
    system_tool = shutil.which("appimagetool")
    if system_tool:
        return Path(system_tool)

    cached_tool = cache_dir / "appimagetool-x86_64.AppImage"
    if not cached_tool.exists():
        url = (
            "https://github.com/AppImage/appimagetool/releases/download/"
            "continuous/appimagetool-x86_64.AppImage"
        )
        print(f"==> Downloading appimagetool from {url}...")
        cache_dir.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(url, cached_tool)
        cached_tool.chmod(0o755)

    return cached_tool


def package_appimage(dist_dir: Path, out_dir: Path, version: str) -> Path:
    print("==> Creating AppImage...")
    with tempfile.TemporaryDirectory(prefix="appimage_") as tmp_dir:
        app_dir = Path(tmp_dir) / "AppDir"
        usr_bin = app_dir / "usr" / "bin"
        usr_share_apps = app_dir / "usr" / "share" / "applications"
        usr_share_icons = app_dir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"

        usr_bin.mkdir(parents=True)
        usr_share_apps.mkdir(parents=True)
        usr_share_icons.mkdir(parents=True)

        # Copy PyInstaller bundle contents
        shutil.copytree(dist_dir, usr_bin, dirs_exist_ok=True)

        icon_src = ROOT_DIR / "assets" / "images" / "image_toolkit_icon.png"
        icon_dest = usr_share_icons / "image-toolkit.png"
        if icon_src.exists():
            shutil.copy2(icon_src, icon_dest)
            shutil.copy2(icon_src, app_dir / "image-toolkit.png")
            shutil.copy2(icon_src, app_dir / ".DirIcon")

        desktop_content = """[Desktop Entry]
Type=Application
Name=Image Toolkit
Comment=Integrated image database and editing framework
Exec=ImageToolkitApp %F
Icon=image-toolkit
Categories=Graphics;Utility;
Terminal=false
"""
        desktop_file = usr_share_apps / "image-toolkit.desktop"
        desktop_file.write_text(desktop_content, encoding="utf-8")
        shutil.copy2(desktop_file, app_dir / "image-toolkit.desktop")

        apprun = app_dir / "AppRun"
        apprun.write_text(
            """#!/bin/sh
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/usr/bin/ImageToolkitApp" "$@"
""",
            encoding="utf-8",
        )
        apprun.chmod(0o755)

        appimagetool = ensure_appimagetool(ROOT_DIR / ".cache")
        out_file = out_dir / f"ImageToolkit-{version}-x86_64.AppImage"

        env = os.environ.copy()
        env["ARCH"] = "x86_64"
        cmd = [str(appimagetool)]
        if "appimagetool-x86_64.AppImage" in str(appimagetool):
            cmd.append("--appimage-extract-and-run")
        cmd.extend([str(app_dir), str(out_file)])

        try:
            subprocess.run(cmd, env=env, check=True)
        except Exception as exc:
            print(f"Warning: AppImage generation failed: {exc}")
            return out_file

        print(f"✅ AppImage built: {out_file}")
        return out_file


def package_deb(dist_dir: Path, out_dir: Path, version: str) -> Path:
    print("==> Creating .deb package...")
    dpkg_deb = shutil.which("dpkg-deb")
    out_file = out_dir / f"image-toolkit_{version}_amd64.deb"
    if not dpkg_deb:
        print("Warning: dpkg-deb not found, skipping .deb package creation")
        return out_file

    with tempfile.TemporaryDirectory(prefix="deb_") as tmp_dir:
        pkg_dir = Path(tmp_dir) / "pkg"
        debian_dir = pkg_dir / "DEBIAN"
        opt_dir = pkg_dir / "opt" / "image-toolkit"
        usr_bin = pkg_dir / "usr" / "bin"
        usr_share_apps = pkg_dir / "usr" / "share" / "applications"
        usr_share_icons = pkg_dir / "usr" / "share" / "icons" / "hicolor" / "256x256" / "apps"

        debian_dir.mkdir(parents=True)
        opt_dir.mkdir(parents=True)
        usr_bin.mkdir(parents=True)
        usr_share_apps.mkdir(parents=True)
        usr_share_icons.mkdir(parents=True)

        control_content = f"""Package: image-toolkit
Version: {version}
Section: graphics
Priority: optional
Architecture: amd64
Maintainer: Image Toolkit Team
Description: Integrated image database and editing framework
"""
        (debian_dir / "control").write_text(control_content, encoding="utf-8")

        shutil.copytree(dist_dir, opt_dir, dirs_exist_ok=True)

        # Executable symlink
        symlink = usr_bin / "image-toolkit"
        if not symlink.exists():
            symlink.symlink_to("/opt/image-toolkit/ImageToolkitApp")

        icon_src = ROOT_DIR / "assets" / "images" / "image_toolkit_icon.png"
        if icon_src.exists():
            shutil.copy2(icon_src, usr_share_icons / "image-toolkit.png")

        desktop_content = """[Desktop Entry]
Type=Application
Name=Image Toolkit
Comment=Integrated image database and editing framework
Exec=/opt/image-toolkit/ImageToolkitApp %F
Icon=image-toolkit
Categories=Graphics;Utility;
Terminal=false
"""
        (usr_share_apps / "image-toolkit.desktop").write_text(
            desktop_content, encoding="utf-8"
        )

        subprocess.run(
            ["dpkg-deb", "--build", "--root-owner-group", str(pkg_dir), str(out_file)],
            check=True,
        )
        print(f"✅ .deb package built: {out_file}")
        return out_file


def main() -> None:
    version = get_app_version()
    out_dir = ROOT_DIR / "dist" / "release"
    out_dir.mkdir(parents=True, exist_ok=True)

    dist_dir = build_pyinstaller()
    package_appimage(dist_dir, out_dir, version)
    package_deb(dist_dir, out_dir, version)
    print(f"🎉 Linux release bundle complete in {out_dir}")


if __name__ == "__main__":
    main()
