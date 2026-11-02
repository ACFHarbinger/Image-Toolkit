"""Apply a saved system preference profile to the open account vault.

Port of the choice the Qt login window offers after a correct password: ``Default``,
``Previous Profile`` (leave the vault as it is) or one saved profile. The vault dict is
changed and saved only when a value actually differs, as in Qt.

Appearance keys (accent colors, font scale, UI density) are Qt-only. A named profile copies
them into the vault preferences for the Qt app; ``Default`` removes them so every consumer falls
back to its own default. The Tauri app uses the returned ``theme`` and ``tab_configurations``.
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_CHOICE = "Default"
PREVIOUS_CHOICE = "Previous Profile"
APPEARANCE_KEYS = ("accent_color_dark", "accent_color_light", "font_scale", "ui_density")


def profile_choices(profiles: list[str]) -> list[str]:
    """The picker entries in the order Qt shows them."""
    if not profiles:
        return []
    return [DEFAULT_CHOICE, PREVIOUS_CHOICE, *sorted(profiles)]


def apply_profile(manager: Any, choice: str) -> dict[str, Any]:
    """Apply ``choice`` to ``manager``'s vault and return what the UI needs. Never returns credentials."""
    stored = manager.load_account_credentials()
    profiles = stored.get("system_preference_profiles")
    profiles = profiles if isinstance(profiles, dict) else {}
    if choice not in (DEFAULT_CHOICE, PREVIOUS_CHOICE) and choice not in profiles:
        raise ValueError("Unknown preference profile.")
    changed = False
    prefs = stored.get("preferences")
    if not isinstance(prefs, dict):
        prefs = {}
        stored["preferences"] = prefs
    if choice == DEFAULT_CHOICE:
        if stored.get("theme", "dark") != "dark" or stored.get("active_tab_configs", {}) != {}:
            stored["theme"] = "dark"
            stored["active_tab_configs"] = {}
            changed = True
        for key in APPEARANCE_KEYS:
            if key in prefs:
                del prefs[key]
                changed = True
    elif choice != PREVIOUS_CHOICE:
        data = profiles[choice] if isinstance(profiles[choice], dict) else {}
        theme = data.get("theme", "dark")
        configs = data.get("active_tab_configs", {})
        if theme != stored.get("theme", "dark") or configs != stored.get("active_tab_configs", {}):
            stored["theme"] = theme
            stored["active_tab_configs"] = configs
            changed = True
        for key in APPEARANCE_KEYS:
            if key in data and data[key] != prefs.get(key):
                prefs[key] = data[key]
                changed = True
    if changed:
        manager.save_data(json.dumps(stored))
    configs = stored.get("active_tab_configs", {})
    return {
        "theme": stored.get("theme", "dark") if stored.get("theme") in ("dark", "light") else "dark",
        "tab_configurations": configs if isinstance(configs, dict) else {},
        "changed": changed,
    }
