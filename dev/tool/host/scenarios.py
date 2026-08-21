"""Scenario Catalog for Automated Reproduction & Regression Testing (Track A4).

Pre-configured reproduction scenarios matching historical crash profiles and stress tests.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Scenario:
    """A named reproduction scenario."""

    name: str
    description: str
    command: List[str]
    tags: List[str]


_SCENARIOS: Dict[str, Scenario] = {
    "media-loader-stress": Scenario(
        name="media-loader-stress",
        description="Run media loader unit & worker stress tests with telemetry enabled",
        command=[sys.executable, "-m", "pytest", "gui/test/test_media_loader_worker.py", "-v"],
        tags=["downloader", "qt", "threading"],
    ),
    "wallpaper-scan-race": Scenario(
        name="wallpaper-scan-race",
        description="Exercise wallpaper dual-panel scan synchronization and monitor restore",
        command=[sys.executable, "-m", "pytest", "gui/test/test_wallpaper_tab.py", "-k", "scan", "-v"],
        tags=["wallpaper", "scanner", "concurrency"],
    ),
    "asp-eval-smoke": Scenario(
        name="asp-eval-smoke",
        description="Run ASP benchmark evaluation pipeline smoke pass",
        command=[sys.executable, "-m", "pytest", "dev/test/development/test_plugins_extended.py", "-k", "asp", "-v"],
        tags=["asp", "evaluator", "benchmark"],
    ),
    "telemetry-span-test": Scenario(
        name="telemetry-span-test",
        description="Run core telemetry nested span allocation and verification tests",
        command=[sys.executable, "-m", "pytest", "backend/test/core/test_telemetry.py", "-v"],
        tags=["telemetry", "core", "spans"],
    ),
}


def list_scenarios() -> List[Scenario]:
    """Return all catalogued reproduction scenarios."""
    return list(_SCENARIOS.values())


def get_scenario(name: str) -> Optional[Scenario]:
    """Look up a reproduction scenario by name."""
    return _SCENARIOS.get(name)


__all__ = ["Scenario", "list_scenarios", "get_scenario"]
