"""Tests for tools/dev/theming/export_css_tokens.py (#574, #575)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPORT_SCRIPT = REPO_ROOT / "tools/dev/theming/export_css_tokens.py"


def test_export_css_tokens_contains_accent(tmp_path: Path) -> None:
    out = tmp_path / "theme-tokens.generated.css"
    proc = subprocess.run(
        [
            sys.executable,
            str(EXPORT_SCRIPT),
            "--surface",
            "docs",
            "--out",
            str(out),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    css = out.read_text(encoding="utf-8")
    assert "--it-color-accent:" in css
    assert "#" in css


def test_paired_export_has_light_root_and_dark_override(tmp_path: Path) -> None:
    out = tmp_path / "theme-tokens.generated.css"
    proc = subprocess.run(
        [
            sys.executable,
            str(EXPORT_SCRIPT),
            "--paired",
            "--out",
            str(out),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    css = out.read_text(encoding="utf-8")
    assert ":root {" in css
    assert ':root[data-theme="dark"] {' in css
    # light defaults come first, dark overrides follow
    assert css.index(":root {") < css.index(':root[data-theme="dark"] {')
    assert "--it-color-accent: #007AFF;" in css  # light
    assert "--it-color-accent: #00bcd4;" in css  # dark


def test_paired_export_rejects_missing_token(tmp_path: Path) -> None:
    broken = tmp_path / "broken-light.json"
    broken.write_text('{"colors": {"accent": "#007AFF"}}', encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(EXPORT_SCRIPT),
            "--paired",
            "--input",
            str(broken),
            "--out",
            str(tmp_path / "out.css"),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
