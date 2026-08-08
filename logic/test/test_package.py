"""Installed-package boundary tests."""

from __future__ import annotations

import sys

import colorization
import features
import learning
import project
import rigging
import temporal
from runtime import NATIVE_COMPUTE_LOCK


def test_flattened_packages_use_top_level_namespaces() -> None:
    packages = (colorization, features, learning, project, rigging, temporal)
    assert {package.__name__ for package in packages} == {
        "colorization",
        "features",
        "learning",
        "project",
        "rigging",
        "temporal",
    }
    assert "manga" not in sys.modules


def test_runtime_coordination_is_owned_by_core_package() -> None:
    assert NATIVE_COMPUTE_LOCK.__class__.__module__ == "_thread"
    assert "backend.src.core.telemetry" not in sys.modules
