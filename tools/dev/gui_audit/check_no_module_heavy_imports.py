"""Lint check for R3.2 / ui-arch-47 (#569): zero module-level heavy imports in gui/src.

Heavy scientific / vision packages (cv2, PIL, numpy, torch, torchvision)
must be imported inside functions, methods, or workers rather than at module
scope, to avoid paying multi-hundred MB RSS and seconds of import time during
desktop startup before login or tab activation.

Usage:
    python tools/dev/gui_audit/check_no_module_heavy_imports.py [gui/src]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Sequence

HEAVY_MODULES = frozenset({"cv2", "PIL", "numpy", "torch", "torchvision"})


def is_type_checking_node(node: ast.AST) -> bool:
    """Check whether an AST node is an `if TYPE_CHECKING:` guard."""
    if not isinstance(node, ast.If):
        return False
    test = node.test
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def find_heavy_imports(root: Path) -> list[str]:
    violations: list[str] = []
    repo_root = root.parent.parent if root.name == "src" else root

    for py_path in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        except Exception as exc:
            violations.append(f"{py_path}: could not parse AST: {exc}")
            continue

        for node in tree.body:
            # Type-checking blocks are eliminated at runtime; ignore them.
            if is_type_checking_node(node):
                continue

            if isinstance(node, ast.Import):
                for alias in node.names:
                    pkg = alias.name.split(".")[0]
                    if pkg in HEAVY_MODULES:
                        try:
                            rel = py_path.relative_to(repo_root)
                        except ValueError:
                            rel = py_path
                        violations.append(
                            f"{rel}:{node.lineno}: module-level '{ast.unparse(node)}' "
                            f"(move inside function/method to keep startup footprint slim)"
                        )
            elif isinstance(node, ast.ImportFrom) and node.module:
                pkg = node.module.split(".")[0]
                if pkg in HEAVY_MODULES:
                    try:
                        rel = py_path.relative_to(repo_root)
                    except ValueError:
                        rel = py_path
                    violations.append(
                        f"{rel}:{node.lineno}: module-level '{ast.unparse(node)}' "
                        f"(move inside function/method to keep startup footprint slim)"
                    )

    return violations


def main(argv: Sequence[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    root = Path(args[0]) if args else Path("gui/src")
    if not root.is_dir():
        print(f"Directory not found: {root}", file=sys.stderr)
        return 2

    violations = find_heavy_imports(root)
    if violations:
        print(f"Found {len(violations)} module-level heavy import(s) in {root}:", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        return 1

    print(f"Clean: 0 module-level heavy imports in {root}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
