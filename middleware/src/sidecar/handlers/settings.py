"""Sidecar handlers for the settings capability (D5 / #851).

Requests route through one process-wide :class:`SettingsService` built
lazily by :func:`settings_service` (JSON file stores under
``~/.image-toolkit/settings/``); tests swap in ``tmp_path`` stores by
monkeypatching the factory, mirroring how the convert dispatch swaps
``ConvertService``. The Cloud Jobs document key gets whole-document
semantics (:mod:`middleware.src.settings.cloud_jobs`): reads return the
full document with defaults filled in, writes validate before they store.
"""

from __future__ import annotations

from typing import Any, Optional

from middleware.src.bridge import BridgeAppError
from middleware.src.cloud.settings import CloudSettings
from middleware.src.settings.cloud_jobs import (
    CLOUD_JOBS_SETTINGS_KEY,
    cloud_settings_document,
    load_cloud_settings,
    save_cloud_settings,
)
from middleware.src.settings.service import SettingsService

_service: Optional[SettingsService] = None


def settings_service() -> SettingsService:
    """The settings service the sidecar routes through (one per process)."""
    global _service
    if _service is None:
        _service = SettingsService()
    return _service


def _invalid_value(key: str, reason: str) -> BridgeAppError:
    return BridgeAppError(
        "settings.invalid_value",
        details={"key": key, "reason": reason},
    )


def _get(service: SettingsService, key: str) -> dict[str, Any]:
    if key == CLOUD_JOBS_SETTINGS_KEY:
        value: Any = load_cloud_settings(service).to_dict()
    else:
        value = service.get(key)
    return {"key": key, "value": value, "scope": service.scope_of(key).value}


def _set(service: SettingsService, key: str, value: Any) -> dict[str, Any]:
    if key == CLOUD_JOBS_SETTINGS_KEY:
        if not isinstance(value, dict):
            raise _invalid_value(key, "expected the CloudSettings document object")
        try:
            stored: Any = save_cloud_settings(service, value)
        except ValueError as exc:
            raise _invalid_value(key, str(exc)) from exc
    else:
        try:
            service.set(key, value)
            stored = value
        except ValueError as exc:
            raise _invalid_value(key, str(exc)) from exc
    return {"key": key, "value": stored, "scope": service.scope_of(key).value}


def handle_settings_get(params: dict[str, Any]) -> dict[str, Any]:
    return _get(settings_service(), params["key"])


def handle_settings_set(params: dict[str, Any]) -> dict[str, Any]:
    return _set(settings_service(), params["key"], params["value"])


def handle_settings_get_many(params: dict[str, Any]) -> dict[str, Any]:
    service = settings_service()
    return {"values": {key: _get(service, key)["value"] for key in params["keys"]}}


def handle_settings_set_many(params: dict[str, Any]) -> dict[str, Any]:
    service = settings_service()
    updates: dict[str, Any] = dict(params["updates"])
    # Validate every write before any store: a rejected field leaves the
    # whole form unsaved instead of half of it.
    for key, value in updates.items():
        if key == CLOUD_JOBS_SETTINGS_KEY:
            if not isinstance(value, dict):
                raise _invalid_value(key, "expected the CloudSettings document object")
            try:
                CloudSettings.from_dict(cloud_settings_document(value))
            except ValueError as exc:
                raise _invalid_value(key, str(exc)) from exc
        else:
            service.validate(key, value)
    for key, value in updates.items():
        _set(service, key, value)
    return {"values": {key: _get(service, key)["value"] for key in updates}}


__all__ = [
    "handle_settings_get",
    "handle_settings_get_many",
    "handle_settings_set",
    "handle_settings_set_many",
    "settings_service",
]
