"""Private helper to ensure submodule package roots and aliases are registered.

CRE, CSG and HIE live under ``middleware.src.{cre,csg,hie}`` (W0-03 phase E, #867)
and need no registration. Only ASP is still registered here until its own move lands.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_submodules_registered() -> None:
    """Ensure the ASP submodule package is registered in sys.path / sys.modules."""
    repo_root = Path(__file__).resolve().parents[3]
    submodules_dir = repo_root / "submodules"
    if not submodules_dir.is_dir():
        return

    try:
        from git.scripts._submodule_bootstrap import register_submodule_packages

        register_submodule_packages(str(repo_root))
    except (ImportError, Exception):
        target = str(submodules_dir / "ASP" / "backend" / "src")
        if target not in sys.path and os.path.isdir(target):
            sys.path.insert(0, target)
