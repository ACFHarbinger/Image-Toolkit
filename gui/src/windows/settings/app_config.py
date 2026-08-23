"""
gui/src/windows/settings/app_config.py
========================================
§5.14C: unified, read-only snapshot of application configuration.

Merges GUI persistence (``AppSettings``/``QSettings``) and backend ASP
pipeline tuning (``get_asp()``/``asp_config.toml``) into one introspectable
object. This is additive, not a replacement -- ``AppSettings`` and
``get_asp()`` remain the source of truth for reads/writes everywhere else.
``AppConfig.capture()`` takes a live snapshot for display/debugging (e.g. a
"Show current config" debug screen), not a cached long-lived object, since
both underlying stores can change at any time.

Lives alongside ``AppSettings`` under ``gui/src/windows/settings/``, not
``gui/src/utils/``: ``gui.src.utils`` is the codebase's documented bottom
utility layer (§5.11A import-linter contract "gui.src.utils must not import
other GUI layers") and this module imports ``AppSettings`` from
``gui.src.windows``, which would break that contract from ``utils``. It also
deliberately lives under ``gui/src/``, not ``backend/src/``: GUI -> backend
is the allowed dependency direction (see
``backend/validation/visualize_module_graph.py``'s layering check) -- the
reverse would be a genuine architectural violation.

Usage::

    from gui.src.windows.settings.app_config import AppConfig

    config = AppConfig.capture()
    print(config)                      # full introspectable dump
    config.asp["ASP_HOLD_THRESHOLD"]   # "0.03" (str, as get_asp() returns)
    config.gui["recursive_scan"]       # True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from asp_backend.core.config import asp_schema, get_asp

from gui.src.constants.windows import _KNOWN_GUI_KEYS
from gui.src.windows.settings.app_settings import AppSettings

# QSettings keys already exposed as typed AppConfig.gui fields -- excluded
# from gui_dynamic_keys so they aren't listed twice.


@dataclass(frozen=True)
class AppConfig:
    """Read-only snapshot of merged GUI + backend ASP configuration.

    ``gui_dynamic_keys`` lists (by name only, not value) every persisted
    QSettings key outside the fixed ``gui`` fields above -- the
    ``session/{class_name}/{key}``, ``splitters/{key}``, and ``labels/{path}``
    namespaces are runtime-created and have no fixed schema to snapshot as
    typed fields.
    """

    asp: dict[str, str] = field(default_factory=dict)
    gui: dict[str, Any] = field(default_factory=dict)
    gui_dynamic_keys: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def capture(cls) -> "AppConfig":
        """Take a live snapshot of current ASP env-vars + QSettings state."""
        asp_values = {key: get_asp(key) for key in asp_schema()}

        gui_values: dict[str, Any] = {
            "mainwindow_geometry": AppSettings.mainwindow_geometry(),
            "recursive_scan": AppSettings.recursive_scan(),
            "favourite_directories": AppSettings.favourite_directories(),
            "mal_fetch_method": AppSettings.mal_fetch_method(),
        }

        dynamic_keys = tuple(sorted(k for k in AppSettings.all_keys() if k not in _KNOWN_GUI_KEYS))

        return cls(asp=asp_values, gui=gui_values, gui_dynamic_keys=dynamic_keys)

    def __str__(self) -> str:
        lines = [
            "AppConfig snapshot:",
            f"  ASP pipeline ({len(self.asp)} keys):",
        ]
        for key, val in sorted(self.asp.items()):
            lines.append(f"    {key} = {val!r}")

        lines.append(f"  GUI static preferences ({len(self.gui)} keys):")
        for key, val in sorted(self.gui.items()):
            lines.append(f"    {key} = {val!r}")

        if self.gui_dynamic_keys:
            lines.append(
                f"  GUI dynamic keys ({len(self.gui_dynamic_keys)}, values omitted "
                "-- per-session/per-path runtime state):"
            )
            for key in self.gui_dynamic_keys:
                lines.append(f"    {key}")

        return "\n".join(lines)


__all__ = ["AppConfig"]
