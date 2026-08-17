"""Registers Python packages supplied by repository submodules.

ASP (Anime-Stitch-Pipeline) exposes flattened source roots and is loaded
under collision-proof aliases. CSG (Cel-Shaded-Generator) also exposes a
flattened core source root; its top-level domain packages are imported
directly:

    asp_backend  -> submodules/ASP/backend/src
    asp_gui      -> submodules/ASP/gui/src
    colorization/learning/... -> submodules/CSG/logic/src
    csg_gui     -> submodules/CSG/gui/src
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
    ("HIE", "middleware", "src"),
    ("HIE", "gui", "src"),
)

# Top-level packages owned by a submodule that share a name with a parent
# repo test package (or another submodule). Pre-importing them here caches
# the correct module in sys.modules so a later bare import (e.g. HIE's
# "from models import ...") resolves to the submodule's package no matter
# what pytest later prepends to sys.path (e.g. backend/test/models
# shadowing the real models package during combined test collection).
# Mirrors the _load_package alias pattern: load the real package under its
# own name so bare imports find it.
_PRELOAD_PACKAGES = (
    ("HIE", "middleware", "src", "models"),
    ("HIE", "middleware", "src", "policies"),
)

# Parent-repo real packages that a test package shadows by name during
# combined collection (e.g. backend/test/models vs backend/src/models, and
# gui/test/models). Pre-importing the real package (and its subpackages)
# caches them so pytest's later package imports resolve to the real code
# rather than the empty test package.
_PRELOAD_PARENT_PACKAGES = (
    "backend.src.models",
    "backend.src.models.data",
    "backend.src.models.wrappers",
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
