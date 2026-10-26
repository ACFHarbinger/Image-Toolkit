"""Cloud Compute setup differential: the Qt providers pane's
DEFAULT_PROVIDERS vs the bridge catalog (T-04 / #920, #883 harness).

The legacy side loads the Qt pane's descriptors by path (a synthetic
package, so the PySide6-importing gui package chain never runs) and
projects the parity fields; the service side projects
``providers_result``. Colors compare as token names — the Qt pane stores
resolved RGB values, which are not part of the contract.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

from middleware.src.services.cloud_setup.providers import providers_result

REPO_ROOT = Path(__file__).resolve().parents[2]
GUI_CLOUD = REPO_ROOT / "gui" / "src" / "windows" / "cloud"
SYNTHETIC = "_gui_cloud_driftguard"

_PARITY_FIELDS = (
    "provider_id",
    "name",
    "badge_text",
    "description",
    "target_service",
    "cpu_shapes",
    "memory_tiers",
    "gpu_options",
    "cost_estimate",
    "cold_start",
    "config_file",
    "is_poc_target",
)


def _qt_providers() -> list[dict[str, object]]:
    for name in (f"{SYNTHETIC}.provider_card", f"{SYNTHETIC}.providers_pane", SYNTHETIC):
        sys.modules.pop(name, None)
    package = types.ModuleType(SYNTHETIC)
    package.__path__ = [str(GUI_CLOUD)]
    sys.modules[SYNTHETIC] = package
    pane = importlib.import_module(f"{SYNTHETIC}.providers_pane")
    return [
        {field: getattr(descriptor, field) for field in _PARITY_FIELDS}
        for descriptor in pane.ProvidersPane.DEFAULT_PROVIDERS
    ]


def pair(tmp: object) -> tuple[dict[str, object], dict[str, object]]:
    legacy = {provider["provider_id"]: provider for provider in _qt_providers()}
    service = {
        provider["provider_id"]: {
            field: provider[field]
            for field in _PARITY_FIELDS
        }
        for provider in providers_result()["providers"]
    }
    return {"providers": legacy}, {"providers": service}
