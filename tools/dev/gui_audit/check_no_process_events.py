"""Audit check for ui-arch-48 / #570: zero live processEvents() calls in gui/src.

Exit criterion for R3.3:
    0 live QApplication.processEvents() in gui/src; replaced by single-shot
    timers or progress facts / Qt event loop.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def find_process_events_calls(root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except Exception as exc:
            violations.append(f"{path}: PARSE ERROR: {exc}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "processEvents":
                    caller = ast.unparse(func)
                    violations.append(f"{path}:{node.lineno}: live {caller}() call")
    return violations


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("gui/src")
    violations = find_process_events_calls(root)
    if violations:
        print(f"Found {len(violations)} live processEvents() call(s):")
        for v in violations:
            print(f"  {v}")
        return 1
    print("Clean: 0 live processEvents() calls in", root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
