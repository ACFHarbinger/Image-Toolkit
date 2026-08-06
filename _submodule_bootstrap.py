"""Registers Python packages supplied by repository submodules.

Anime-Stitch-Pipeline still exposes flattened source roots, so it is loaded
under collision-proof aliases. Cel-Shaded-Generator owns conventional wrapped
packages and is imported by those stable public names:

    asp_backend  -> submodules/Anime-Stitch-Pipeline/backend/src
    asp_gui      -> submodules/Anime-Stitch-Pipeline/gui/src
    cel_shaded_generator     -> submodules/Cel-Shaded-Generator/src
    cel_shaded_generator_gui -> submodules/Cel-Shaded-Generator/gui/src
"""

from __future__ import annotations

import importlib.util
import os
import sys

_ALIASES = {
    "asp_backend": ("Anime-Stitch-Pipeline", "backend", "src"),
    "asp_gui": ("Anime-Stitch-Pipeline", "gui", "src"),
}

_PACKAGE_ROOTS = (
    ("Cel-Shaded-Generator", "src"),
    ("Cel-Shaded-Generator", "gui", "src"),
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
