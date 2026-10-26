"""Private helper to ensure submodule package roots and aliases are registered."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def ensure_submodules_registered() -> None:
    """Ensure submodule packages (ASP, CSG, CRE) are registered in sys.path / sys.modules.

    HIE lives at ``middleware.src.hie`` (#1037) and is not registered here.
    """
    repo_root = Path(__file__).resolve().parents[3]
    submodules_dir = repo_root / "submodules"
    if not submodules_dir.is_dir():
        return

    # 1. Base submodule bootstrap (ASP, CSG). HIE is middleware.src.hie (#1037).
    try:
        from git.scripts._submodule_bootstrap import register_submodule_packages

        register_submodule_packages(str(repo_root))
    except (ImportError, Exception):
        for rel_parts in [
            ("ASP", "backend", "src"),
            ("CSG", "logic", "src"),
        ]:
            target = str(submodules_dir.joinpath(*rel_parts))
            if target not in sys.path and os.path.isdir(target):
                sys.path.insert(0, target)

    # 2. CRE integration without shadowing middleware.src
    cre_src = str(submodules_dir / "CRE" / "src")
    if os.path.isdir(cre_src):
        try:
            import src

            if hasattr(src, "__path__") and cre_src not in src.__path__:
                src.__path__.append(cre_src)
            if hasattr(src, "core") and hasattr(src.core, "__path__"):
                cre_core = os.path.join(cre_src, "core")
                if cre_core not in src.core.__path__:
                    src.core.__path__.append(cre_core)
        except (ImportError, Exception):
            pass
