"""First-party plugin registry.

Each plugin module exposes a module-level `plugin` object (or the name
given in its manifest entry point). Discovery enumerates these; this package
is the canonical home for first-party plugins until a plugin manager grows.
"""

from __future__ import annotations

from . import telemetry_workbench

FIRST_PARTY = [
    telemetry_workbench.plugin,
]

__all__ = ["FIRST_PARTY"]
