"""One settings service shared by both GUIs (W0-16 / #880).

Qt-free counterpart of ``gui/src/preferences`` — scopes, keys, conflict
detection and backed-up legacy migration live here; the Qt shell's
``PreferenceStore`` and the Tauri shell both delegate to this package.

Public surface::

    from middleware.src.settings import (
        ConflictPolicy,
        SettingsService,
        SettingScope,
        migrate_legacy,
    )
"""

from .conflicts import (
    ConflictError,
    ConflictPolicy,
    MigrationConflictError,
    SettingsConflict,
)
from .keys import KNOWN_DEFINITIONS, SettingDefinition, SettingKeys, definition_for, infer_scope
from .migration import MigrationError, MigrationReport, migrate_legacy
from .scopes import SettingScope
from .service import SettingsService

__all__ = [
    "ConflictError",
    "ConflictPolicy",
    "KNOWN_DEFINITIONS",
    "MigrationConflictError",
    "MigrationError",
    "MigrationReport",
    "SettingsConflict",
    "SettingsService",
    "SettingDefinition",
    "SettingKeys",
    "SettingScope",
    "definition_for",
    "infer_scope",
    "migrate_legacy",
]
