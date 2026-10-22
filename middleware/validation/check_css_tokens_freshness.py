"""Check generated theme-token CSS freshness (W0-07 / #871).

The checked-in ``frontend/src/shell/theme-tokens.generated.css`` and the
docs website's ``docs/website/src/styles/theme-tokens.generated.css``
must match what ``tools/dev/theming/export_css_tokens.py`` regenerates
from ``gui/src/theming/tokens/{light,dark}.json`` — same pattern as the
contracts ``--check``. A drifted file means the tokens were edited without
re-running the generator; run ``npm run gen:theme-tokens`` (frontend) or
``gen:theme-tokens`` (docs/website) and commit the result.

Example:
    >>> python middleware/validation/check_css_tokens_freshness.py
    >>> python middleware/validation/check_css_tokens_freshness.py --root /path/to/repo
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

EXPORTER_REL = Path("tools/dev/theming/export_css_tokens.py")
TOKENS_REL = Path("gui/src/theming/tokens")
GENERATED = [
    (
        Path("frontend/src/shell/theme-tokens.generated.css"),
        "paired",
        None,
    ),
    (
        Path("docs/website/src/styles/theme-tokens.generated.css"),
        "single",
        "docs",
    ),
]


def _load_exporter(root: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("export_css_tokens", root / EXPORTER_REL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {root / EXPORTER_REL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expected_css(exporter: ModuleType, root: Path, mode: str, surface: str | None) -> str:
    load = exporter._load_tokens
    if mode == "paired":
        return exporter.paired_tokens_to_css(
            load(root / TOKENS_REL / "light.json"),
            load(root / TOKENS_REL / "dark.json"),
        )
    return exporter.tokens_to_css(load(root / TOKENS_REL / "dark.json"), surface=surface)


def check(root: Path) -> list[str]:
    exporter = _load_exporter(root)
    problems: list[str] = []
    for rel, mode, surface in GENERATED:
        target = root / rel
        if not target.is_file():
            problems.append(f"{rel}: missing (run the theme-token generator)")
            continue
        if target.read_text(encoding="utf-8") != _expected_css(exporter, root, mode, surface):
            problems.append(f"{rel}: stale (regenerate with the theme-token generator)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    problems = check(args.root)
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}", file=sys.stderr)
        return 1
    print("theme-token CSS freshness: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
