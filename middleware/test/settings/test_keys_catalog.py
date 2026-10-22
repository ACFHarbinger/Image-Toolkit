"""Drift guard: the shared key catalog matches the gui catalog (W0-16 / #880).

Loads the Qt-free ``gui/src/preferences/definitions.py`` and ``scopes.py``
by path (a synthetic package, so the PySide6-importing gui package
``__init__`` chain never runs) and asserts key-for-key parity with the
shared catalog: same keys, same scopes, same defaults, same types.
A key change must land in both catalogs in the same PR.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

from middleware.src.settings.keys import KNOWN_DEFINITIONS
from middleware.src.settings.scopes import SettingScope

REPO_ROOT = Path(__file__).resolve().parents[3]
GUI_PREFERENCES = REPO_ROOT / "gui" / "src" / "preferences"
SYNTHETIC = "_gui_preferences_driftguard"


def _gui_definitions():
    for name in (f"{SYNTHETIC}.scopes", f"{SYNTHETIC}.definitions", SYNTHETIC):
        sys.modules.pop(name, None)
    package = types.ModuleType(SYNTHETIC)
    package.__path__ = [str(GUI_PREFERENCES)]
    sys.modules[SYNTHETIC] = package
    return importlib.import_module(f"{SYNTHETIC}.definitions")


def _catalog_rows(definitions, scope_of):
    return {d.key: (scope_of(d.scope), d.default, d.value_type) for d in definitions}


def test_keys_scopes_and_types_match_the_gui_catalog() -> None:
    gui_defs = _gui_definitions()

    def gui_scope(scope):
        return scope.value

    def shared_scope(scope):
        return scope.value

    gui_rows = _catalog_rows(gui_defs.ALL_KNOWN_DEFINITIONS, gui_scope)
    shared_rows = _catalog_rows(KNOWN_DEFINITIONS, shared_scope)
    changed = {k for k in shared_rows.keys() & gui_rows.keys() if shared_rows[k] != gui_rows[k]}
    assert shared_rows == gui_rows, (
        "the shared settings catalog drifted from gui/src/preferences:"
        f" only-shared={set(shared_rows) - set(gui_rows)},"
        f" only-gui={set(gui_rows) - set(shared_rows)},"
        f" changed={changed}"
    )


def test_scopes_are_preserved() -> None:
    gui_scopes = importlib.import_module(f"{SYNTHETIC}.scopes").PreferenceScope
    assert {m.name: m.value for m in SettingScope} == {m.name: m.value for m in gui_scopes}
