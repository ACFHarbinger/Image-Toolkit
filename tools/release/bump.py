#!/usr/bin/env python3
"""``just release::bump <semver>`` — single-source-of-truth version bump.

The canonical version is the root ``pyproject.toml`` ``[project].version``.
This rewrites every derived source to match, prints the resulting diff, and
does NOT commit or tag:

* ``pyproject.toml``            (root, ``[project].version`` — canonical)
* ``backend/pyproject.toml``    (the dist the running app reads at runtime)
* ``gui/pyproject.toml``
* ``git/pyproject.toml``
* ``pixi.toml``                 (``[workspace].version``)
* ``package.json``              (``version``)
* ``app/android/build.gradle.kts``  (``versionName`` + derived ``versionCode``)

All rewrites are prepared before anything is written, so a validation failure
leaves the tree untouched.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]

SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _rewrite_toml_version(text: str, version: str, section: str) -> str:
    lines = text.splitlines(keepends=True)
    in_section = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{section}]"
            continue
        if in_section and re.match(r'^version\s*=\s*"[^"]*"', stripped):
            indent = line[: len(line) - len(line.lstrip())]
            lines[i] = f'{indent}version = "{version}"\n'
            return "".join(lines)
    raise RuntimeError(f"no version line in [{section}] section")


def _rewrite_package_json(text: str, version: str) -> str:
    new, count = re.subn(
        r'(?m)^(\s*)"version"\s*:\s*"[^"]*"',
        lambda m: f'{m.group(1)}"version": "{version}"',
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError('no "version" key')
    return new


def _rewrite_gradle(text: str, version: str) -> str:
    major, minor, patch = (int(part) for part in version.split("."))
    version_code = major * 10000 + minor * 100 + patch
    new, count = re.subn(
        r"(?m)^(\s*)versionCode\s*=\s*\d+",
        lambda m: f"{m.group(1)}versionCode = {version_code}",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("no versionCode line")
    new, count = re.subn(
        r'(?m)^(\s*)versionName\s*=\s*"[^"]*"',
        lambda m: f'{m.group(1)}versionName = "{version}"',
        new,
        count=1,
    )
    if count != 1:
        raise RuntimeError("no versionName line")
    return new


def _targets(version: str) -> list[tuple[Path, Callable[[str], str]]]:
    project = lambda text: _rewrite_toml_version(text, version, "project")  # noqa: E731
    return [
        (REPO_ROOT / "pyproject.toml", project),
        (REPO_ROOT / "backend/pyproject.toml", project),
        (REPO_ROOT / "gui/pyproject.toml", project),
        (REPO_ROOT / "git/pyproject.toml", project),
        (REPO_ROOT / "pixi.toml", lambda text: _rewrite_toml_version(text, version, "workspace")),
        (REPO_ROOT / "package.json", lambda text: _rewrite_package_json(text, version)),
        (REPO_ROOT / "app/android/build.gradle.kts", lambda text: _rewrite_gradle(text, version)),
    ]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: just release::bump <semver>   e.g. just release::bump 1.0.0")
        return 2
    new_version = sys.argv[1]
    if not SEMVER_RE.match(new_version):
        print(
            f"error: '{new_version}' is not a valid SemVer release version "
            "(expected X.Y.Z, numeric parts, no leading zeros)"
        )
        return 2

    rewrites: list[tuple[Path, str]] = []
    for path, fn in _targets(new_version):
        try:
            original = path.read_text(encoding="utf-8")
            rewritten = fn(original)
        except (OSError, RuntimeError) as exc:
            print(f"error: {path.relative_to(REPO_ROOT)}: {exc}")
            return 1
        if rewritten != original:
            rewrites.append((path, rewritten))

    if not rewrites:
        print(f"nothing to do — all version sources already at {new_version}")
        return 0

    for path, rewritten in rewrites:
        path.write_text(rewritten, encoding="utf-8")

    changed = [str(path.relative_to(REPO_ROOT)) for path, _ in rewrites]
    print(f"Image Toolkit version bumped to {new_version}:")
    subprocess.run(["git", "diff", "--"] + changed, cwd=REPO_ROOT, check=False)
    print(
        "\nreview the diff above; commit manually (this recipe never commits or tags). "
        "Suggested: git add -u && git commit -m 'release: bump version to "
        f"{new_version}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
