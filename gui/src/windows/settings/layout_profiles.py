"""Window Layout and State Profiles Manager (GUI/UX §2.32)."""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QWidget

from .app_settings import AppSettings


class LayoutProfileManager:
    """Manages saving, loading, listing, and switching named window geometry and splitter layout profiles."""

    SETTINGS_PREFIX = "layout_profiles"

    @classmethod
    def list_profiles(cls) -> List[str]:
        """Return list of saved layout profile names."""
        raw = AppSettings.get(f"{cls.SETTINGS_PREFIX}/index")
        if not raw:
            return ["Default"]
        try:
            if isinstance(raw, str):
                names = json.loads(raw)
            else:
                names = list(raw)
            if "Default" not in names:
                names.insert(0, "Default")
            return [str(n) for n in names]
        except Exception:
            return ["Default"]

    @classmethod
    def save_profile(
        cls,
        name: str,
        geometry: Optional[bytes] = None,
        splitters: Optional[Dict[str, bytes]] = None,
        window: Optional[QWidget] = None,
    ) -> bool:
        """Save a layout profile under *name*."""
        name = name.strip()
        if not name:
            return False

        profile_data: Dict[str, Any] = {}

        if geometry is not None:
            profile_data["geometry"] = base64.b64encode(geometry).decode("ascii")
        elif window is not None:
            try:
                geom = bytes(window.saveGeometry())
                profile_data["geometry"] = base64.b64encode(geom).decode("ascii")
            except Exception:
                pass

        splitters_dict: Dict[str, str] = {}
        if splitters is not None:
            for k, v in splitters.items():
                splitters_dict[k] = base64.b64encode(v).decode("ascii")
        else:
            for key in AppSettings.all_keys():
                if key.startswith("splitters/") or key.startswith("splitter/"):
                    raw = AppSettings.get(key)
                    if raw:
                        try:
                            splitters_dict[key] = base64.b64encode(bytes(raw)).decode("ascii")
                        except Exception:
                            pass
        profile_data["splitters"] = splitters_dict

        AppSettings.set(f"{cls.SETTINGS_PREFIX}/data/{name}", json.dumps(profile_data))

        # Update index
        profiles = cls.list_profiles()
        if name not in profiles:
            profiles.append(name)
            AppSettings.set(f"{cls.SETTINGS_PREFIX}/index", json.dumps(profiles))

        return True

    @classmethod
    def load_profile(cls, name: str) -> Optional[Dict[str, Any]]:
        """Load profile dictionary containing raw geometry bytes and splitter bytes."""
        name = name.strip()
        raw = AppSettings.get(f"{cls.SETTINGS_PREFIX}/data/{name}")
        if not raw:
            return None
        try:
            data = json.loads(raw)
            result: Dict[str, Any] = {}
            if "geometry" in data:
                result["geometry"] = base64.b64decode(data["geometry"])
            splitters: Dict[str, bytes] = {}
            for k, v in data.get("splitters", {}).items():
                splitters[k] = base64.b64decode(v)
            result["splitters"] = splitters
            return result
        except Exception:
            return None

    @classmethod
    def apply_profile(cls, name: str, window: Optional[QWidget] = None) -> bool:
        """Apply the saved layout profile to *window* and write splitter states to AppSettings."""
        profile = cls.load_profile(name)
        if not profile:
            return False

        if "geometry" in profile and window is not None:
            try:
                window.restoreGeometry(QByteArray(profile["geometry"]))
            except Exception:
                pass

        for key, state_bytes in profile.get("splitters", {}).items():
            try:
                AppSettings.set(key, QByteArray(state_bytes))
            except Exception:
                pass

        return True

    @classmethod
    def delete_profile(cls, name: str) -> bool:
        """Delete a named layout profile (cannot delete 'Default')."""
        if name == "Default":
            return False
        AppSettings.set(f"{cls.SETTINGS_PREFIX}/data/{name}", None)
        profiles = cls.list_profiles()
        if name in profiles:
            profiles.remove(name)
            AppSettings.set(f"{cls.SETTINGS_PREFIX}/index", json.dumps(profiles))
            return True
        return False

    @classmethod
    def export_profiles_json(cls) -> str:
        """Export all profiles to a JSON string."""
        exported = {}
        for name in cls.list_profiles():
            raw = AppSettings.get(f"{cls.SETTINGS_PREFIX}/data/{name}")
            if raw:
                try:
                    exported[name] = json.loads(raw)
                except Exception:
                    pass
        return json.dumps(exported, indent=2)

    @classmethod
    def import_profiles_json(cls, json_str: str) -> int:
        """Import profiles from a JSON string, returns count of imported profiles."""
        try:
            data = json.loads(json_str)
            if not isinstance(data, dict):
                return 0
            count = 0
            for name, pdata in data.items():
                if isinstance(pdata, dict):
                    AppSettings.set(f"{cls.SETTINGS_PREFIX}/data/{name}", json.dumps(pdata))
                    profiles = cls.list_profiles()
                    if name not in profiles:
                        profiles.append(name)
                        AppSettings.set(f"{cls.SETTINGS_PREFIX}/index", json.dumps(profiles))
                    count += 1
            return count
        except Exception:
            return 0


__all__ = ["LayoutProfileManager"]
