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
