"""Enforce R1.1 worker-base adoption (ui-arch-34/#556) in ``gui/src/helpers/``.

Three hard rules (fail CI, block merge):

1. No raw ``QThread``/``QRunnable`` subclasses — every worker derives from
   ``BaseQThreadWorker`` / ``BaseQRunnableWorker`` (``base.py`` itself is
   the only file allowed to name them as bases).
2. No ``def run()`` override in a ``Base*`` subclass — worker logic goes in
   ``_execute()``; overriding ``run()`` would bypass the GC guard and the
   ``finished``/``error`` delivery in ``base.py``.
3. No legacy result/error signal names — the vocabulary is
   ``finished`` / ``error`` / ``progress`` plus per-item stream signals.
   Banned: ``finished_signal``, ``error_signal``, ``sig_finished``,
   ``work_finished``, ``sync_finished``, ``scan_finished``, ``finished_ok``.
   (``scan_error`` stays: the image/video scanners' mid-scan warning
   channel, documented on the workers.)

Example:
    >>> python backend/validation/check_worker_base.py
    >>> python backend/validation/check_worker_base.py --root /path/to/repo
"""

import argparse
import ast
import sys
from pathlib import Path

HELPERS_REL = Path("gui/src/helpers")
BASE_FILE = "base.py"

RAW_BASES = frozenset({"QThread", "QRunnable"})
BASE_WORKERS = frozenset({"BaseQThreadWorker", "BaseQRunnableWorker"})
LEGACY_SIGNALS = frozenset({
    "finished_signal",
    "error_signal",
    "sig_finished",
    "work_finished",
    "sync_finished",
    "scan_finished",
    "finished_ok",
})


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def check_file(path: Path) -> list[str]:
    """Apply rules 1-3 to one helper module."""
    violations: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return [f"{path}:{exc.lineno}: cannot parse ({exc.msg})"]
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [_base_name(b) for b in node.bases]
        if path.name != BASE_FILE and any(b in RAW_BASES for b in bases):
            raw = next(b for b in bases if b in RAW_BASES)
            violations.append(
                f"{path}:{node.lineno}: class {node.name} subclasses raw "
                f"{raw} — derive from BaseQThreadWorker/BaseQRunnableWorker"
            )
        if any(b in BASE_WORKERS for b in bases):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name == "run":
                    violations.append(
                        f"{path}:{child.lineno}: {node.name}.run() overrides "
                        f"the base run() — put worker logic in _execute()"
                    )
        for child in node.body:
            if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                if child.target.id in LEGACY_SIGNALS:
                    violations.append(
                        f"{path}:{child.lineno}: legacy signal name "
                        f"{child.target.id} — use finished/error/progress"
                    )
            elif isinstance(child, ast.Assign):
                names = [t.id for t in child.targets if isinstance(t, ast.Name)]
                if any(n in LEGACY_SIGNALS for n in names):
                    violations.append(
                        f"{path}:{child.lineno}: legacy signal name "
                        f"{names} — use finished/error/progress"
                    )
    return violations


def main() -> int:
    """Walk ``gui/src/helpers/`` and report violations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args()
    root = Path(args.root)
    helpers = root / HELPERS_REL
    violations: list[str] = []
    for path in sorted(helpers.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        violations.extend(check_file(path))
    for violation in violations:
        print(violation)
    if violations:
        print(f"\n{len(violations)} worker-base violation(s) — see R1.1 (#556).")
        return 1
    print("worker-base adoption clean (R1.1).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
