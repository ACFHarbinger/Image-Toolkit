#!/usr/bin/env python3
"""Copy the project venv and middleware into the Tauri sidecar resource.

The packaged app launches this directory. It does not record the checkout
path into the binary. Run from ``frontend/src-tauri`` before ``tauri build``.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SOURCE_VENV = REPO / ".venv"
SOURCE_MIDDLEWARE = REPO / "middleware"
DEST = Path(__file__).resolve().parents[1] / "resources" / "sidecar-runtime"
SKIP_DIR_NAMES = {"__pycache__", ".pytest_cache", "test", "tests"}


def _ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in SKIP_DIR_NAMES or name.endswith(".pyc")}
    return ignored


def _rewrite_pyvenv(venv: Path) -> None:
    config = venv / "pyvenv.cfg"
    if not config.is_file():
        return
    python = venv / "bin" / "python"
    lines: list[str] = []
    for line in config.read_text(encoding="utf-8").splitlines():
        if line.startswith("executable =") or line.startswith("command ="):
            lines.append(f"executable = {python}")
            continue
        lines.append(line)
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not (SOURCE_VENV / "bin" / "python").is_file() and not (SOURCE_VENV / "bin" / "python3").is_file():
        print(f"sidecar runtime requires {SOURCE_VENV}", file=sys.stderr)
        return 1
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    shutil.copytree(SOURCE_VENV, DEST / ".venv", symlinks=True, ignore=_ignore)
    shutil.copytree(SOURCE_MIDDLEWARE, DEST / "middleware", symlinks=True, ignore=_ignore)
    for native in REPO.glob("backend*.so"):
        shutil.copy2(native, DEST / native.name)
    _rewrite_pyvenv(DEST / ".venv")
    (DEST / "RUNTIME.json").write_text('{"layout":"sidecar-runtime"}\n', encoding="utf-8")
    print(f"staged sidecar runtime at {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
