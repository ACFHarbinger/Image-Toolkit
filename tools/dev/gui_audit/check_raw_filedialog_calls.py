"""Advisory lint for ui-arch-29/#551: raw ``QFileDialog.get*`` static calls.

``apply_patch()`` (``gui/src/file_dialog_patch.py``) monkeypatches
``QFileDialog.get*`` in place on first import of ``gui.src``, so every
existing call site is already routed through the non-native dialog at
runtime -- this is *not* a correctness bug. It is a defense-in-depth /
readability check: a call site that imports ``my_get*`` directly from
``gui.src.file_dialog_patch`` can't regress even if some future test or
entry point ever constructs a ``QFileDialog`` before ``gui.src`` is
imported, and it's clearer at the call site that a non-native dialog is
being used on purpose.

Not wired into CI (the ~74 pre-existing sites are tracked debt, not a
regression gate) -- see gui_refactoring.md R2.a for the migration. Use this
to make sure NEW call sites don't add to the count, and to track the
baseline as it's paid down.

Usage: python check_raw_filedialog_calls.py [gui/src]
"""
import ast
import sys
from pathlib import Path

_RAW_GETTERS = frozenset(
    {"getExistingDirectory", "getOpenFileName", "getOpenFileNames", "getSaveFileName"}
)


def find_violations(root: Path) -> list[str]:
    violations = []
    patch_file = root / "file_dialog_patch.py"
    for py_path in sorted(root.rglob("*.py")):
        if py_path == patch_file:
            continue
        tree = ast.parse(py_path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if (
                isinstance(fn, ast.Attribute)
                and fn.attr in _RAW_GETTERS
                and isinstance(fn.value, ast.Name)
                and fn.value.id == "QFileDialog"
            ):
                violations.append(
                    f"{py_path.relative_to(root.parent.parent)}:{node.lineno}: "
                    f"raw QFileDialog.{fn.attr}() (prefer my_{fn.attr} from "
                    f"gui.src.file_dialog_patch)"
                )
    return violations


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("gui/src")
    violations = find_violations(root)
    for v in violations:
        print(v)
    print(f"\n{len(violations)} raw QFileDialog.get* call site(s) (advisory, not CI-blocking).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
