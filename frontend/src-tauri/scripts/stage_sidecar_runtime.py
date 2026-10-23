#!/usr/bin/env python3
"""Stage a standalone Python distribution, dependencies and bridge resources."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEST = Path(__file__).resolve().parents[1] / "resources" / "sidecar-runtime"


def _ignore(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in {"__pycache__", ".pytest_cache"} or name.endswith(".pyc")}


def stage(repo: Path, venv: Path, destination: Path) -> None:
    source_python = venv / "bin" / "python"
    info = json.loads(
        subprocess.check_output(
            [
                str(source_python),
                "-I",
                "-c",
                "import json,sys,sysconfig; print(json.dumps({'base':sys.base_prefix,"
                "'version':f'{sys.version_info.major}.{sys.version_info.minor}',"
                "'site':sysconfig.get_path('purelib')}))",
            ],
            text=True,
        )
    )
    base = Path(info["base"])
    version = info["version"]
    # A system /usr prefix is not a redistributable Python installation.
    if base in {Path("/usr"), Path("/usr/local"), Path("/")}:
        raise ValueError("staging requires a standalone Python distribution (for example uv-managed Python)")
    if destination.exists():
        raise FileExistsError(f"remove the previous staged runtime first: {destination}")
    destination.mkdir(parents=True)
    try:
        python_root = destination / "python"
        # Dereference interpreter/library links; never retain a build-machine target.
        shutil.copytree(base, python_root, symlinks=False, ignore=_ignore)
        site = python_root / "lib" / f"python{version}" / "site-packages"
        shutil.copytree(Path(info["site"]), site, dirs_exist_ok=True, symlinks=False, ignore=_ignore)
        for name in ("middleware", "contracts"):
            shutil.copytree(repo / name, destination / name, symlinks=False, ignore=_ignore)
        for native in repo.glob("backend*.so"):
            shutil.copy2(native, destination / native.name)
        python = python_root / "bin" / f"python{version}"
        # -I removes build/user PYTHONPATH and virtualenv assumptions. Discover resources
        # exactly as the installed child does, from its module's relocated path.
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                "import sys; sys.path.insert(0,sys.argv[1]); "
                "assert sys.prefix == str(__import__('pathlib').Path(sys.argv[1]) / 'python'); "
                "from middleware.src.sidecar.server import SidecarServer; SidecarServer()",
                str(destination.resolve()),
            ],
            cwd=destination,
            check=True,
        )
        (destination / "RUNTIME.json").write_text(json.dumps({"layout": "sidecar-runtime", "python": version}) + "\n")
    except BaseException:
        shutil.rmtree(destination)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--venv", type=Path)
    parser.add_argument("--destination", type=Path, default=DEST)
    args = parser.parse_args()
    scratch = Path.home() / "Downloads/Data/Tests"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sidecar-stage-", dir=scratch) as temporary:
        staged = Path(temporary) / "runtime"
        stage(args.repo.resolve(), (args.venv or args.repo / ".venv").resolve(), staged)
        # Only replace the previous bundle after the new runtime passes its smoke check.
        if args.destination.exists():
            shutil.rmtree(args.destination)
        args.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged), args.destination)
    print(f"staged sidecar runtime at {args.destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
