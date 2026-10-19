#!/usr/bin/env python3
"""Launch the standalone Qt demonstration application.

Installed packages need no path setup. The two source roots are added only
when this file is run directly from a repository checkout.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for source_root in (_REPO_ROOT / "logic" / "src",):
    source = str(source_root)
    if source not in sys.path:
        sys.path.insert(0, source)


def _load_gui_package() -> None:
    """Register the flattened GUI source root under its installed name."""
    source_root = _REPO_ROOT / "gui" / "src"
    spec = importlib.util.spec_from_file_location(
        "csg_gui",
        source_root / "__init__.py",
        submodule_search_locations=[str(source_root)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load CSG GUI package from {source_root}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["csg_gui"] = module
    spec.loader.exec_module(module)


def main() -> int:
    _load_gui_package()
    from csg_gui.app import main as run_app

    return run_app()


if __name__ == "__main__":
    raise SystemExit(main())
