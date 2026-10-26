"""Installed-package boundary tests."""

from __future__ import annotations

import sys

import middleware.src.csg.colorization as colorization
import middleware.src.csg.features as features
import middleware.src.csg.learning as learning
import middleware.src.csg.project as project
import middleware.src.csg.rigging as rigging
import middleware.src.csg.temporal as temporal
from middleware.src.csg.runtime import NATIVE_COMPUTE_LOCK


def test_flattened_packages_use_top_level_namespaces() -> None:
    packages = (colorization, features, learning, project, rigging, temporal)
    assert {package.__name__ for package in packages} == {
        "middleware.src.csg.colorization",
        "middleware.src.csg.features",
        "middleware.src.csg.learning",
        "middleware.src.csg.project",
        "middleware.src.csg.rigging",
        "middleware.src.csg.temporal",
    }
    assert "manga" not in sys.modules


def test_runtime_coordination_is_owned_by_core_package() -> None:
    assert NATIVE_COMPUTE_LOCK.__class__.__module__ == "_thread"
    # middleware/test/conftest.py already imports toolkit telemetry. The engine
    # lock must still not depend on it (#1036).
    import ast
    from pathlib import Path

    import middleware.src.csg.runtime as runtime

    tree = ast.parse(Path(runtime.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert imported == ["__future__", "threading"]
    assert "telemetry" not in runtime.__dict__
