#!/usr/bin/env python3
"""Launch the standalone Qt demonstration application.

Installed packages need no path setup. A checkout run adds the toolkit root
so ``middleware.src.csg`` imports resolve (#1036).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
# Engine moved to middleware/src/csg (#1036). Checkout runs need the toolkit
# root importable; installed Image-Toolkit already provides it.
_TOOLKIT_ROOT = str(_REPO_ROOT.parent.parent)
if _TOOLKIT_ROOT not in sys.path:
    sys.path.insert(0, _TOOLKIT_ROOT)


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
