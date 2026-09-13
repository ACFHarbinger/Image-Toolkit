"""Detect unauthorized inline styling in gui/src (#564).

Flags ``setStyleSheet(`` outside ``theming/`` and ``styles/``, and inline
``#rrggbb`` hex literals outside ``theming/``, ``styles/``, and ``constants/``.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ALLOWLIST_PATH = Path(__file__).resolve().parent / "styling_allowlist.txt"

STYLE_SHEET_ALLOWED_PREFIXES = (
    "gui/src/theming/",
    "gui/src/styles/",
)

HEX_ALLOWED_PREFIXES = (
    "gui/src/theming/",
    "gui/src/styles/",
    "gui/src/constants/",
)

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b")


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _load_allowlist() -> set[str]:
    if not ALLOWLIST_PATH.is_file():
        return set()
    entries: set[str] = set()
    for line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        entries.add(line.replace("\\", "/"))
    return entries


def _write_allowlist(paths: set[str]) -> None:
    lines = [
        "# One repo-relative path per line; files listed here are skipped by the styling audit.",
        "# Regenerate with: python tools/dev/gui_audit/check_unauthorized_styling.py --update-baseline gui/src",
        "",
    ]
    lines.extend(sorted(paths))
    lines.append("")
    ALLOWLIST_PATH.write_text("\n".join(lines), encoding="utf-8")


def _prefix_allowed(rel: str, prefixes: tuple[str, ...]) -> bool:
    return any(rel.startswith(p) for p in prefixes)


def _has_raw_stylesheet_arg(node: ast.Call) -> bool:
    if not node.args:
        return True
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return True
    if isinstance(arg, ast.JoinedStr):
        return True
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add):
        return True
    if isinstance(arg, ast.Attribute):
        return True
    if isinstance(arg, ast.Name):
        return True
    return False


class _StyleVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stylesheet_calls: list[int] = []

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        name = None
        if isinstance(func, ast.Attribute) and func.attr == "setStyleSheet":
            name = "setStyleSheet"
        elif isinstance(func, ast.Name) and func.id == "setStyleSheet":
            name = "setStyleSheet"
        if name == "setStyleSheet" and _has_raw_stylesheet_arg(node):
            # Allow setStyleSheet(qss(...)) and setStyleSheet(color(...)) — Call args.
            if node.args and isinstance(node.args[0], ast.Call):
                func_node = node.args[0].func
                if isinstance(func_node, ast.Name) and func_node.id in {"qss", "color"}:
                    pass
                elif isinstance(func_node, ast.Attribute) and func_node.attr in {"qss", "color"}:
                    pass
                else:
                    self.stylesheet_calls.append(node.lineno)
            else:
                self.stylesheet_calls.append(node.lineno)
        self.generic_visit(node)


def scan_file(path: Path, root: Path) -> tuple[list[str], list[str]]:
    rel = _rel(path, root)
    src = path.read_text(encoding="utf-8")
    violations_ss: list[str] = []
    violations_hex: list[str] = []

    if not _prefix_allowed(rel, STYLE_SHEET_ALLOWED_PREFIXES):
        try:
            tree = ast.parse(src)
        except SyntaxError:
            tree = None
        if tree is not None:
            visitor = _StyleVisitor()
            visitor.visit(tree)
            for lineno in visitor.stylesheet_calls:
                violations_ss.append(f"{rel}:{lineno}: setStyleSheet")

    if not _prefix_allowed(rel, HEX_ALLOWED_PREFIXES):
        for match in HEX_RE.finditer(src):
            line = src.count("\n", 0, match.start()) + 1
            violations_hex.append(f"{rel}:{line}: hex {match.group(0)}")

    return violations_ss, violations_hex


def scan_tree(root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        ss, hx = scan_file(path, REPO_ROOT)
        violations.extend(ss)
        violations.extend(hx)
    return violations


def _filter_allowlist(violations: list[str], allowlist: set[str]) -> list[str]:
    filtered: list[str] = []
    for v in violations:
        rel = v.split(":", 1)[0]
        if rel not in allowlist:
            filtered.append(v)
    return filtered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default="gui/src",
        help="Path under repo root to scan (default: gui/src)",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Regenerate styling_allowlist.txt from current violations outside gui/src/components/",
    )
    args = parser.parse_args(argv)

    scan_root = REPO_ROOT / args.root
    if not scan_root.is_dir():
        print(f"Not a directory: {scan_root}", file=sys.stderr)
        return 2

    violations = scan_tree(scan_root)
    allowlist = _load_allowlist()

    if args.update_baseline:
        outside_components = {v.split(":", 1)[0] for v in violations if not v.startswith("gui/src/components/")}
        _write_allowlist(outside_components)
        print(f"Updated allowlist: {len(outside_components)} paths -> {ALLOWLIST_PATH}")
        return 0

    filtered = _filter_allowlist(violations, allowlist)
    components = [v for v in filtered if v.startswith("gui/src/components/")]
    other = [v for v in filtered if not v.startswith("gui/src/components/")]

    print(f"styling violations: {len(filtered)} total ({len(components)} in components/, {len(other)} elsewhere)")
    for v in filtered:
        print(v)

    if components or other:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
