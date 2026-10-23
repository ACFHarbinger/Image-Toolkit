"""Unit tests for middleware/validation/check_css_tokens_freshness.py (W0-07 / #871)."""

from __future__ import annotations

import shutil
from pathlib import Path

from middleware.validation.check_css_tokens_freshness import (
    _expected_css,
    _load_exporter,
    check,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _mini_repo(root: Path) -> None:
    (root / "tools/dev/theming").mkdir(parents=True)
    shutil.copy(
        REPO_ROOT / "tools/dev/theming/export_css_tokens.py",
        root / "tools/dev/theming/export_css_tokens.py",
    )
    shutil.copytree(REPO_ROOT / "gui/src/theming/tokens", root / "gui/src/theming/tokens")
    # keep the docs surface fresh so only the frontend drift is reported
    exporter = _load_exporter(root)
    docs = root / "docs/website/src/styles/theme-tokens.generated.css"
    docs.parent.mkdir(parents=True)
    docs.write_text(_expected_css(exporter, root, "single", "docs"), encoding="utf-8")


def test_shipped_generated_files_are_fresh() -> None:
    assert check(REPO_ROOT) == []


def test_stale_generated_file_is_reported(tmp_path: Path) -> None:
    _mini_repo(tmp_path)
    target = tmp_path / "frontend/src/shell/theme-tokens.generated.css"
    target.parent.mkdir(parents=True)
    target.write_text(":root { --it-color-accent: #deadbe; }\n", encoding="utf-8")
    problems = check(tmp_path)
    assert len(problems) == 1
    assert "stale" in problems[0]


def test_missing_generated_file_is_reported(tmp_path: Path) -> None:
    _mini_repo(tmp_path)
    problems = check(tmp_path)  # docs surface was pre-seeded by _mini_repo
    assert len(problems) == 1
    assert "missing" in problems[0]
