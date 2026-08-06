"""Registers the Anime-Stitch-Pipeline and Cel-Shaded-Generator submodules'
Python packages under explicit aliases in ``sys.modules``.

Both submodules' ``src/`` directories were deliberately flattened (no single
wrapping "animation"/"manga" directory -- see their own moon/ROADMAP.md) so
that e.g. ``core/``, ``rendering/``, ``gui/src/tabs/`` are direct children.
That means simply adding each src/ root to ``sys.path`` would expose bare,
collision-prone top-level names (both submodules have their own ``core/``
and both GUI trees have ``tabs/``/``elements/``/``helpers/``), and the two
submodules would clobber each other. Instead, each package directory is
loaded under a fixed alias via ``importlib``, independent of its on-disk
directory name:

    asp_backend  -> submodules/Anime-Stitch-Pipeline/backend/src
    asp_gui      -> submodules/Anime-Stitch-Pipeline/gui/src
    manga        -> submodules/Cel-Shaded-Generator/src
    manga_gui    -> submodules/Cel-Shaded-Generator/gui/src
"""

from __future__ import annotations

import importlib.util
import os
import sys

_ALIASES = {
    "asp_backend": ("Anime-Stitch-Pipeline", "backend", "src"),
    "asp_gui": ("Anime-Stitch-Pipeline", "gui", "src"),
    "manga": ("Cel-Shaded-Generator", "src"),
    "manga_gui": ("Cel-Shaded-Generator", "gui", "src"),
}


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
