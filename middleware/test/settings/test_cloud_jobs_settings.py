"""Cloud Jobs settings document on the settings service (D5 / #851)."""

from __future__ import annotations

from pathlib import Path

import pytest

from middleware.src.settings import cloud_jobs
from middleware.src.settings.adapters import JsonFileStore, MemoryStore
from middleware.src.settings.scopes import SettingScope
from middleware.src.settings.service import SettingsService


def _service(tmp_path: Path) -> SettingsService:
    return SettingsService(
        stores={
            SettingScope.DEVICE: JsonFileStore(tmp_path / "device.json"),
            SettingScope.ACCOUNT: JsonFileStore(tmp_path / "account.json"),
            SettingScope.SESSION: MemoryStore(),
        }
    )


def test_key_is_account_scoped() -> None:
    assert cloud_jobs.CLOUD_JOBS_SETTINGS_KEY in {d.key for d in (cloud_jobs.CLOUD_JOBS_SETTINGS_DEFINITION,)}
    assert cloud_jobs.CLOUD_JOBS_SETTINGS_DEFINITION.scope is SettingScope.ACCOUNT
    from middleware.src.settings.keys import definition_for

    assert definition_for(cloud_jobs.CLOUD_JOBS_SETTINGS_KEY) is cloud_jobs.CLOUD_JOBS_SETTINGS_DEFINITION


def test_absent_document_reads_as_defaults(tmp_path: Path) -> None:
    service = _service(tmp_path)
    settings = cloud_jobs.load_cloud_settings(service)
    defaults = cloud_jobs.cloud_settings_document(None)
    assert settings == cloud_jobs.load_cloud_settings(service)
    assert defaults["packing_mode"] == "one_to_one"
    assert defaults["fallback_enabled"] is False
    assert defaults["notify_desktop"] is True


def test_partial_document_merges_with_defaults(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.set(cloud_jobs.CLOUD_JOBS_SETTINGS_KEY, {"packing_mode": "parallel"})
    settings = cloud_jobs.load_cloud_settings(service)
    assert settings.packing_mode == "parallel"
    # Unstored fields fall back to shipped defaults, not to blanks.
    assert settings.max_concurrent_jobs == 4
    assert settings.notify_desktop is True


def test_save_round_trips_the_whole_document(tmp_path: Path) -> None:
    service = _service(tmp_path)
    stored = cloud_jobs.save_cloud_settings(service, {"monthly_cap_usd": 250.0, "notify_webhook_url": "https://hooks.example/j"})
    assert stored["monthly_cap_usd"] == 250.0
    assert stored["notify_webhook_url"] == "https://hooks.example/j"
    assert cloud_jobs.load_cloud_settings(service).monthly_cap_usd == 250.0
    # The stored document is complete, so a fresh service reads it back.
    again = SettingsService(
        stores={SettingScope.ACCOUNT: JsonFileStore(tmp_path / "account.json")}
    )
    assert cloud_jobs.load_cloud_settings(again).notify_webhook_url == "https://hooks.example/j"


def test_invalid_document_is_rejected_at_save(tmp_path: Path) -> None:
    service = _service(tmp_path)
    with pytest.raises(ValueError):
        cloud_jobs.save_cloud_settings(service, {"packing_mode": "sneaky", "max_attempts": 0})
    # Nothing was written.
    assert not service.contains(cloud_jobs.CLOUD_JOBS_SETTINGS_KEY)


def test_corrupt_stored_document_reads_as_defaults(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.set(cloud_jobs.CLOUD_JOBS_SETTINGS_KEY, {"packing_mode": "no-longer-a-mode"})
    assert cloud_jobs.load_cloud_settings(service).packing_mode == "one_to_one"
