"""Cloud Jobs settings persistence on the #880 settings service (D5 / #851).

The D5 surface — caps, thresholds, retention, packing, fallback,
notifications and regions — is one ``CloudSettings`` document stored under
the ACCOUNT-scoped ``cloud_jobs/settings`` key. Reads always return the
full document (stored fields over :class:`CloudSettings` defaults), so a
shipped default change reaches the UI without a migration. Writes are
validated whole through ``CloudSettings.from_dict`` before they reach the
store, so an invalid field never persists.

The key lives in the extension catalog (``register_definitions``), not in
``KNOWN_DEFINITIONS``: that list is parity-frozen against the W0-20 gui
catalog, and the frozen ``gui/src`` copy must not learn new keys. The risk
*rule editor* is deliberately not here: rules persist in ``cloud_jobs.db``
(``middleware.src.cloud.risk.store``), not in the settings service, and
rides the jobs capability when that surface opens.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

from middleware.src.cloud.settings import CloudSettings
from middleware.src.settings.keys import SettingDefinition, register_definitions
from middleware.src.settings.scopes import SettingScope

if TYPE_CHECKING:  # pragma: no cover - circular only under type checking
    from middleware.src.settings.service import SettingsService

CLOUD_JOBS_SETTINGS_KEY = "cloud_jobs/settings"

CLOUD_JOBS_SETTINGS_DEFINITION = SettingDefinition(
    key=CLOUD_JOBS_SETTINGS_KEY,
    scope=SettingScope.ACCOUNT,
    default=None,
    value_type=dict,
    description="Cloud Jobs settings document (CloudSettings fields, D5 / #851)",
)

register_definitions([CLOUD_JOBS_SETTINGS_DEFINITION])

#: T-04 / #920: per-provider non-secret setup config (region/endpoint
#: preferences). Real credentials live in the vault and never transit the
#: bridge; attaching them rides the vault unlock (#918 / #879).
CLOUD_SETUP_PROFILES_KEY = "cloud_setup/profiles"
CLOUD_SETUP_PROFILES_DEFINITION = SettingDefinition(
    key=CLOUD_SETUP_PROFILES_KEY,
    scope=SettingScope.ACCOUNT,
    default=None,
    value_type=dict,
    description="Cloud Compute per-provider non-secret setup config (T-04 / #920)",
)

register_definitions([CLOUD_SETUP_PROFILES_DEFINITION])


def cloud_settings_document(stored: Mapping[str, Any] | None) -> dict[str, Any]:
    """The full settings document: defaults overlaid with stored fields."""
    defaults = CloudSettings().to_dict()
    if stored is None:
        return defaults
    defaults.update({k: v for k, v in stored.items() if k in defaults})
    return defaults


def load_cloud_settings(service: SettingsService) -> CloudSettings:
    """Read the persisted CloudSettings; absent or partial docs fall back
    field-by-field to shipped defaults. A document that no longer
    validates (e.g. written by an older build against different rules)
    reads as defaults rather than dead-ending the Settings view; the next
    save overwrites it with a valid document."""
    stored = service.get(CLOUD_JOBS_SETTINGS_KEY, None)
    if stored is None:
        return CloudSettings()
    try:
        return CloudSettings.from_dict(cloud_settings_document(stored))
    except ValueError:
        return CloudSettings()


def save_cloud_settings(service: SettingsService, data: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the whole document, persist it, and return what was stored."""
    settings = CloudSettings.from_dict(cloud_settings_document(data))
    document = settings.to_dict()
    service.set(CLOUD_JOBS_SETTINGS_KEY, document)
    return document


__all__ = [
    "CLOUD_JOBS_SETTINGS_DEFINITION",
    "CLOUD_JOBS_SETTINGS_KEY",
    "CLOUD_SETUP_PROFILES_DEFINITION",
    "CLOUD_SETUP_PROFILES_KEY",
    "cloud_settings_document",
    "load_cloud_settings",
    "save_cloud_settings",
]
