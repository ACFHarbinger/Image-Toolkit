"""Private helper to ensure submodule package roots and aliases are registered.

CSG lives at ``middleware.src.csg`` (#1036) and is not inserted onto ``sys.path``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_submodules_registered() -> None:
    """Ensure submodule packages (ASP, CSG, CRE) are registered in sys.path / sys.modules.

    HIE lives at ``middleware.src.hie`` (#1037) and is not registered here.
    """Ensure ASP, HIE, and CRE submodule packages are registered in sys.path / sys.modules."""
    """Ensure submodule packages (ASP, HIE, CSG) are registered in sys.path / sys.modules.

    CRE no longer needs registration: it lives at ``middleware/src/cre`` since
    the W0-03 phase E relocation (#867).
    """
    repo_root = Path(__file__).resolve().parents[3]
    submodules_dir = repo_root / "submodules"
    if not submodules_dir.is_dir():
        return

    # 1. Base submodule bootstrap (ASP, CSG). HIE is middleware.src.hie (#1037).
    # 1. Base submodule bootstrap (ASP, HIE). CSG is middleware.src.csg (#1036).
    try:
        from git.scripts._submodule_bootstrap import register_submodule_packages

        register_submodule_packages(str(repo_root))
    except (ImportError, Exception):
        for rel_parts in [
            ("ASP", "backend", "src"),
            ("CSG", "logic", "src"),
            ("HIE", "middleware", "src"),
        ]:
            target = str(submodules_dir.joinpath(*rel_parts))
            if target not in sys.path and os.path.isdir(target):
                sys.path.insert(0, target)
