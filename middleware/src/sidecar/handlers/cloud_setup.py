"""Sidecar handlers for the cloud_setup capability (T-04 / #920)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.cloud_setup.providers import providers_result


def handle_cloud_setup_providers() -> dict[str, Any]:
    return providers_result()


__all__ = ["handle_cloud_setup_providers"]
