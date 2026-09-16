#!/usr/bin/env python3
"""Package the Windows PySide6 desktop app into a zip artifact.

Designed to run inside the pixi (conda-forge) dev environment on a Windows
runner. The conda env provides MSVC, OpenCV, sqlcipher, libsodium, and all
Python runtime deps. The C++ base extension and native crypto library are
built before invoking PyInstaller.
"""

from __future__ import annotations

import os
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


def get_conda_prefix() -> str:
    """Return the active conda/pixi environment prefix."""
    return os.path.dirname(os.path.dirname(sys.executable))


def build_crypto_lib() -> None:
    """Build the native crypto library (libitk_crypto.dll) against conda's OpenSSL."""
    build_dir = ROOT_DIR / "build" / "crypto"
    build_dir.mkdir(parents=True, exist_ok=True)
    conda_prefix = get_conda_prefix()

    dll_path = build_dir / "libitk_crypto.dll"
    source = ROOT_DIR / "base" / "src" / "secret" / "itk_crypto.c"

    print("==> Building native crypto library (libitk_crypto.dll)...")
    subprocess.run(
        [
            "cl",
            "/O2",
            "/LD",
            f"/I{os.path.join(conda_prefix, 'include')}",
            str(source),
            f"/Fe{dll_path}",
            "/link",
            f"/LIBPATH:{os.path.join(conda_prefix, 'lib')}",
            "libcrypto.lib",
        ],
        cwd=ROOT_DIR,
        check=True,
    )
    print(f"    Built: {dll_path}")


def build_base_extension() -> None:
    """Build the C++ base pybind11 extension using cmake (MSVC/Ninja)."""
    print("==> Building C++ base extension (MSVC/Ninja)...")
    conda_prefix = get_conda_prefix()

    # Include vcpkg installed dir in CMAKE_PREFIX_PATH so CMakeLists.txt
    # find_path/find_library can locate SQLCipher (installed via vcpkg,
    # not on conda-forge for win-64).
    vcpkg_dir = os.environ.get("VCPKG_INSTALLED_DIR", "C:/vcpkg/installed")
    vcpkg_triplet = os.path.join(vcpkg_dir, "x64-windows")
    prefix_path = f"{conda_prefix};{vcpkg_triplet}"

    subprocess.run(
        [
            "cmake",
            "-B", "build/base",
            "base/",
            "-G", "Ninja",
            "-DCMAKE_BUILD_TYPE=Release",
            f"-DCMAKE_PREFIX_PATH={prefix_path}",
        ],
        cwd=ROOT_DIR,
        check=True,
    )
    subprocess.run(
        ["cmake", "--build", "build/base", "--parallel"],
        cwd=ROOT_DIR,
        check=True,
    )

    # Stage the built .pyd where imports and the spec expect it.
    base_libs = list((ROOT_DIR / "build" / "base").glob("base*.pyd"))
    if not base_libs:
        raise RuntimeError("C++ base extension build failed: no base*.pyd found")
    for lib in base_libs:
        shutil.copy2(lib, ROOT_DIR)
        site_pkgs = subprocess.check_output(
            [sys.executable, "-c", "import site; print(site.getsitepackages()[0])"],
            text=True,
        ).strip()
        shutil.copy2(lib, site_pkgs)
    print("    Built and staged base extension.")


def build_pyinstaller() -> Path:
    """Run PyInstaller and return the dist directory."""
    dist_dir = ROOT_DIR / "dist" / "ImageToolkit"
    vcpkg_dir = Path(os.environ.get("VCPKG_INSTALLED_DIR", "C:/vcpkg/installed"))
    vcpkg_bin_dir = vcpkg_dir / "x64-windows" / "bin"
    if vcpkg_bin_dir.is_dir():
        # The base extension links SQLCipher from vcpkg. Make its DLLs
        # discoverable while PyInstaller resolves binary dependencies.
        os.environ["PATH"] = f"{vcpkg_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
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
    """Create a zip archive of the built application."""
    print("==> Creating zip archive...")
    zip_base = out_dir / f"ImageToolkit-{version}-windows-x86_64"
    archive_path = shutil.make_archive(
        str(zip_base),
        "zip",
        root_dir=dist_dir.parent,
        base_dir=dist_dir.name,
    )
    print(f"    Windows release archive created: {archive_path}")
    return Path(archive_path)


def main() -> None:
    version = get_app_version()
    out_dir = ROOT_DIR / "dist" / "release"
    out_dir.mkdir(parents=True, exist_ok=True)

    build_crypto_lib()
    build_base_extension()
    dist_dir = build_pyinstaller()
    package_zip(dist_dir, out_dir, version)
    print(f"Windows release bundle complete in {out_dir}")


if __name__ == "__main__":
    main()
