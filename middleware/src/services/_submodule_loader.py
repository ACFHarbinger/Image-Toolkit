"""Private helper to ensure submodule package roots and aliases are registered.

CRE, CSG, HIE and ASP's engine live under ``middleware.src.{cre,csg,hie,stitching}``
(W0-03 phase E, #867). Only the frozen Qt GUI aliases are still bootstrapped here.
"""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_submodules_registered() -> None:
    """Register the remaining submodule aliases in sys.path / sys.modules."""
    repo_root = Path(__file__).resolve().parents[3]
    submodules_dir = repo_root / "submodules"
    if not submodules_dir.is_dir():
        return

    try:
        from git.scripts._submodule_bootstrap import register_submodule_packages

        register_submodule_packages(str(repo_root))
    except (ImportError, Exception):
        stitching_dir = str(repo_root / "middleware" / "src" / "stitching")
        if stitching_dir not in sys.path and (repo_root / "middleware" / "src" / "stitching").is_dir():
            sys.path.insert(0, stitching_dir)
