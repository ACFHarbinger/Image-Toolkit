"""Settings window and configurations — lazily re-exported (issues #530, #573, R3.6)."""

from __future__ import annotations

import importlib

_LAZY_EXPORTS = {
    "AppConfig": ".app_config",
    "AppSettings": ".app_settings",
    "SettingsBackend": ".settings_backend",
    "SettingsWindow": ".settings_window",
    "persist_splitter": ".splitter_persistence",
    "load_thumbnail_size": ".thumbnail_size",
    "save_thumbnail_size": ".thumbnail_size",
}

__all__ = [
    "AppConfig",
    "AppSettings",
    "SettingsBackend",
    "SettingsWindow",
    "persist_splitter",
    "load_thumbnail_size",
    "save_thumbnail_size",
]


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(_LAZY_EXPORTS[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
