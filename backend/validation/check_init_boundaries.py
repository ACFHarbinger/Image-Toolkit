"""Guard the gui package-initializer import boundaries (issue #530, D9).

Two hard rules (fail CI, block merge):

1. No ``from X import *`` in any ``gui/src/**/__init__.py`` — the wildcard
   hubs (``components``, ``constants``, ``tabs``) were converted to explicit
   re-exports; a star import here fails this check.
2. No eager submodule imports at the top level of
   ``gui/src/windows/__init__.py`` — it must stay a cheap lazy facade
   (PEP 562 ``__getattr__`` over ``_LAZY_EXPORTS``), otherwise importing the
   package pulls ``MainWindow`` and the world at import time. Only imports
   that cannot execute eagerly are allowed at module level: function-local
   imports and ``if TYPE_CHECKING:`` blocks. As a consistency pin, every
   ``__all__`` entry must have a matching ``_LAZY_EXPORTS`` key.

Example:
    >>> python backend/validation/check_init_boundaries.py
    >>> python backend/validation/check_init_boundaries.py --root /path/to/repo
"""

import argparse
import ast
import sys
from pathlib import Path


def _is_type_checking_if(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
    )


def check_no_star_imports(init_path: Path) -> list[str]:
    """Rule 1: no star imports in a package initializer."""
    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(
            a.name == "*" for a in node.names
        ):
            violations.append(f"{init_path}:{node.lineno}: star import is forbidden here")
    return violations


def check_windows_init_lazy(init_path: Path) -> list[str]:
    """Rule 2: windows/__init__.py must not eagerly import gui submodules."""
    tree = ast.parse(init_path.read_text(encoding="utf-8"))
    violations = []
    for node in tree.body:
        if _is_type_checking_if(node):
            continue
        if isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                violations.append(
                    f"{init_path}:{node.lineno}: eager relative import "
                    f"(move it behind __getattr__)"
                )
            elif node.module and node.module.split(".")[0] == "gui":
                violations.append(
                    f"{init_path}:{node.lineno}: eager gui import "
                    f"(move it behind __getattr__)"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "gui":
                    violations.append(
                        f"{init_path}:{node.lineno}: eager gui import "
                        f"(move it behind __getattr__)"
                    )
    violations.extend(check_lazy_map_consistent(init_path, tree))
    return violations


def _literal_str_list(node: ast.AST) -> list[str] | None:
    if isinstance(node, (ast.List, ast.Tuple)) and all(
        isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts
    ):
        return [e.value for e in node.elts]
    return None


def _literal_str_dict_keys(node: ast.AST) -> list[str] | None:
    if isinstance(node, ast.Dict) and all(
        isinstance(k, ast.Constant) and isinstance(k.value, str) for k in node.keys
    ):
        return [k.value for k in node.keys]
    return None


def check_lazy_map_consistent(init_path: Path, tree: ast.AST) -> list[str]:
    """Every __all__ entry needs a _LAZY_EXPORTS key (same file)."""
    all_names = exports = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "__all__":
                all_names = _literal_str_list(node.value)
            elif isinstance(target, ast.Name) and target.id == "_LAZY_EXPORTS":
                exports = _literal_str_dict_keys(node.value)
    if all_names is None or exports is None:
        return [
            f"{init_path}:1: __all__ and _LAZY_EXPORTS must be plain "
            f"literals so this check can verify them"
        ]
    missing = [n for n in all_names if n not in exports]
    return [
        f"{init_path}:1: __all__ entry {name!r} has no _LAZY_EXPORTS mapping"
        for name in missing
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root)
    gui_src = root / "gui" / "src"
    violations = []

    for init_path in sorted(gui_src.rglob("__init__.py")):
        violations.extend(check_no_star_imports(init_path))

    windows_init = gui_src / "windows" / "__init__.py"
    if windows_init.exists():
        violations.extend(check_windows_init_lazy(windows_init))
    else:
        violations.append(f"{windows_init}: missing")

    for violation in violations:
        print(violation)
    if violations:
        print(f"{len(violations)} init-boundary violation(s); see issue #530.")
        return 1
    print("init boundaries OK: no star imports, windows/__init__ stays lazy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
