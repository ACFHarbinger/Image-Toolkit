"""Deprecated alias: the Python package moved to ``middleware`` (Tauri migration W0-01, #865).

``backend.<x>`` resolves to the *same module object* as ``middleware.<x>`` (not a
copy), so ``patch("backend.src...")`` targets and the submodules' imports keep
working. Removed by W0-02 (#866), which gives the ``backend`` name to the C++
core.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys
import warnings

_OLD, _NEW = "backend", "middleware"


class _AliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(_OLD + "."):
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return importlib.import_module(_NEW + spec.name[len(_OLD):])

    def exec_module(self, module):
        return None


if not any(isinstance(f, _AliasFinder) for f in sys.meta_path):
    sys.meta_path.insert(0, _AliasFinder())

warnings.warn("`backend` was renamed to `middleware`; this alias is removed by W0-02 (#866).",
              DeprecationWarning, stacklevel=2)


def __getattr__(name: str):
    return importlib.import_module(f"{_NEW}.{name}")
