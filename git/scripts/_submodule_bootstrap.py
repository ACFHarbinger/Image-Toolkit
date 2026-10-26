"""Registers Python packages supplied by repository submodules.

ASP (Anime-Stitch-Pipeline) exposes flattened source roots and is loaded
under collision-proof aliases. CSG's colorization engine lives at
``middleware.src.csg`` (#1036), not on ``sys.path``. The frozen Qt GUI is
still loaded under an alias:

    asp_backend  -> submodules/ASP/backend/src
    asp_gui      -> submodules/ASP/gui/src
    csg_gui      -> submodules/CSG/gui/src
"""

from __future__ import annotations

import contextlib
import importlib.util
import os
import sys

_ALIASES = {
    "asp_backend": ("ASP", "backend", "src"),
    "asp_gui": ("ASP", "gui", "src"),
    "csg_gui": ("CSG", "gui", "src"),
}

_PACKAGE_ROOTS = (
    ("CSG", "logic", "src"),
    # Qt GUI stays at submodules/HIE/gui until the final removal PR.
    # The engine is middleware.src.hie (#1037), not a path root: a bare
    # ``import models`` would shadow middleware.src.models.
    ("HIE", "middleware", "src"),
    ("HIE", "gui", "src"),
)

# HIE models/policies preloads were removed in #1037 with the bare imports
# they existed for. Do not preload a top-level ``models`` — it would shadow
# middleware.src.models now that HIE is middleware.src.hie.models.
_PRELOAD_PACKAGES: tuple[tuple[str, ...], ...] = ()

# Parent-repo real packages that a test package shadows by name during
# combined collection (e.g. middleware/test/models vs middleware/src/models, and
# gui/test/models). Pre-importing the real package (and its subpackages)
# caches them so pytest's later package imports resolve to the real code
# rather than the empty test package.
_PRELOAD_PARENT_PACKAGES = (
    "middleware.src.models",
    "middleware.src.models.data",
    "middleware.src.models.wrappers",
)


def _load_package(alias: str, src_dir: str) -> None:
    if alias in sys.modules or not os.path.isdir(src_dir):
        return
    init_file = os.path.join(src_dir, "__init__.py")
    spec = importlib.util.spec_from_file_location(
        alias, init_file, submodule_search_locations=[src_dir]
    )
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)


def register_submodule_packages(repo_root: str) -> None:
    """Idempotent -- safe to call from every entry point / conftest.py."""
    for alias, parts in _ALIASES.items():
        _load_package(alias, os.path.join(repo_root, "submodules", *parts))
    for parts in _PACKAGE_ROOTS:
        package_root = os.path.join(repo_root, "submodules", *parts)
        if os.path.isdir(package_root) and package_root not in sys.path:
            sys.path.insert(0, package_root)
    for parts in _PRELOAD_PACKAGES:
        package_root = os.path.join(repo_root, "submodules", *parts[:-1])
        if os.path.isdir(package_root) and package_root not in sys.path:
            sys.path.insert(0, package_root)
        _load_package(parts[-1], os.path.join(package_root, parts[-1]))
    for dotted in _PRELOAD_PARENT_PACKAGES:
        with contextlib.suppress(ImportError):
            __import__(dotted)  # subpackage may not exist in this checkout
