"""Locate the absorbed ASP package for benchmark scripts.

These scripts used to live at ``backend/benchmark/*.py`` and registered
``parents[1] / "src"`` as ``asp_backend`` (the ASP submodule's
``backend/src``). They now live at ``middleware/benchmark/asp/*.py``.
The package is ``middleware/src/stitching``, and the Image-Toolkit root
is three parents above this file.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_THIS = Path(__file__).resolve()


def repo_root() -> Path:
    """Image-Toolkit checkout that contains this benchmark tree."""
    return _THIS.parents[3]


def stitching_src() -> Path:
    """Python package imported as ``middleware.src.stitching`` and ``asp_backend``."""
    return repo_root() / "middleware" / "src" / "stitching"


def ensure_repo_on_path() -> Path:
    root = repo_root()
    root_s = str(root)
    if root_s not in sys.path:
        sys.path.insert(0, root_s)
    return root


def load_package(alias: str, src_dir: Path) -> None:
    """Register ``src_dir`` as ``alias`` when it is not already imported.

    A no-op when pytest (or another bootstrap) has already bound the alias,
    and when ``src_dir`` is not a package. The pre-move path
    ``middleware/benchmark/src`` is not a package; callers must pass
    :func:`stitching_src` instead of assuming that old relative path.
    """
    if alias in sys.modules or not src_dir.is_dir():
        return
    init = src_dir / "__init__.py"
    if not init.is_file():
        return
    spec = importlib.util.spec_from_file_location(
        alias, init, submodule_search_locations=[str(src_dir)]
    )
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)


def install_asp_backend() -> Path:
    """Put the repo root on ``sys.path`` and alias ``asp_backend`` to stitching."""
    ensure_repo_on_path()
    src = stitching_src()
    load_package("asp_backend", src)
    return src


def load_benchmark_aliases() -> Path:
    """Alias both ``asp_backend`` and ``asp_backend_benchmark`` for the bench script."""
    src = install_asp_backend()
    load_package("asp_backend_benchmark", _THIS.parent)
    return src
