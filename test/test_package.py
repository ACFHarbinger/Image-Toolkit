"""Installed-package boundary tests."""

from __future__ import annotations

import sys

import cel_shaded_generator
from cel_shaded_generator.runtime import NATIVE_COMPUTE_LOCK


def test_public_package_uses_stable_namespace() -> None:
    assert cel_shaded_generator.__name__ == "cel_shaded_generator"
    assert "manga" not in sys.modules


def test_runtime_coordination_is_owned_by_core_package() -> None:
    assert NATIVE_COMPUTE_LOCK.__class__.__module__ == "_thread"
    assert "backend.src.core.telemetry" not in sys.modules
