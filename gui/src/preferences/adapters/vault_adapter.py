"""gui/src/preferences/adapters/vault_adapter.py
=============================================
Vault adapter for account-scoped preferences (§1.1, #525).
"""

from __future__ import annotations

import copy
from threading import RLock
from typing import Any

from .base import PreferenceAdapter


class VaultPreferenceAdapter(PreferenceAdapter):
    """Adapter backed by account credentials dictionary and VaultManager.

    Manages user profile preferences. Enforces volatility rules for guest sessions:
    guest data is held in-memory and never written to an account vault.
    """

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        vault_manager: Any = None,
        account_name: str = "",
    ) -> None:
        self._lock = RLock()
        self._credentials: dict[str, Any] = copy.deepcopy(credentials) if credentials else {}
        self._vault_manager = vault_manager
        self._account_name = account_name

    def set_credentials(
        self,
        credentials: dict[str, Any],
        vault_manager: Any = None,
        account_name: str = "",
    ) -> None:
        """Attach active account credentials to this adapter."""
        with self._lock:
            self._credentials = copy.deepcopy(credentials)
            if vault_manager is not None:
                self._vault_manager = vault_manager
            if account_name:
                self._account_name = account_name

    @property
    def is_guest(self) -> bool:
        with self._lock:
            if self._vault_manager is not None:
                return bool(getattr(self._vault_manager, "is_guest", False))
            return False

    def _normalize_key(self, key: str) -> tuple[str, str]:
        """Return (section, subkey).

        For example:
          'preferences/recursive_scan' -> ('preferences', 'recursive_scan')
          'theme' -> ('top', 'theme')
        """
        if key.startswith("preferences/"):
            return ("preferences", key[len("preferences/"):])
        if "/" in key:
            prefix, subkey = key.split("/", 1)
            return (prefix, subkey)
        return ("top", key)

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            section, subkey = self._normalize_key(key)
            if section == "preferences":
                prefs = self._credentials.get("preferences", {})
                if isinstance(prefs, dict) and subkey in prefs:
                    return copy.deepcopy(prefs[subkey])
                if subkey in self._credentials:
                    return copy.deepcopy(self._credentials[subkey])
            elif section == "top":
                if subkey in self._credentials:
                    return copy.deepcopy(self._credentials[subkey])
                prefs = self._credentials.get("preferences", {})
                if isinstance(prefs, dict) and subkey in prefs:
                    return copy.deepcopy(prefs[subkey])
            else:
                sec_dict = self._credentials.get(section, {})
                if isinstance(sec_dict, dict) and subkey in sec_dict:
                    return copy.deepcopy(sec_dict[subkey])

            return default

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            section, subkey = self._normalize_key(key)
            if section == "preferences":
                if "preferences" not in self._credentials or not isinstance(self._credentials["preferences"], dict):
                    self._credentials["preferences"] = {}
                self._credentials["preferences"][subkey] = copy.deepcopy(value)
            elif section == "top":
                self._credentials[subkey] = copy.deepcopy(value)
            else:
                if section not in self._credentials or not isinstance(self._credentials[section], dict):
                    self._credentials[section] = {}
                self._credentials[section][subkey] = copy.deepcopy(value)

    def contains(self, key: str) -> bool:
        with self._lock:
            section, subkey = self._normalize_key(key)
            if section == "preferences":
                prefs = self._credentials.get("preferences", {})
                if isinstance(prefs, dict) and subkey in prefs:
                    return True
                return subkey in self._credentials
            if section == "top":
                if subkey in self._credentials:
                    return True
                prefs = self._credentials.get("preferences", {})
                return isinstance(prefs, dict) and subkey in prefs
            sec_dict = self._credentials.get(section, {})
            return isinstance(sec_dict, dict) and subkey in sec_dict

    def remove(self, key: str) -> None:
        with self._lock:
            section, subkey = self._normalize_key(key)
            if section == "preferences":
                prefs = self._credentials.get("preferences", {})
                if isinstance(prefs, dict):
                    prefs.pop(subkey, None)
                self._credentials.pop(subkey, None)
            elif section == "top":
                self._credentials.pop(subkey, None)
                prefs = self._credentials.get("preferences", {})
                if isinstance(prefs, dict):
                    prefs.pop(subkey, None)
            else:
                sec_dict = self._credentials.get(section, {})
                if isinstance(sec_dict, dict):
                    sec_dict.pop(subkey, None)

    def all_keys(self) -> list[str]:
        with self._lock:
            keys: list[str] = []
            for k, v in self._credentials.items():
                if isinstance(v, dict):
                    for subk in v.keys():
                        keys.append(f"{k}/{subk}")
                else:
                    keys.append(k)
            return keys

    def get_credentials(self) -> dict[str, Any]:
        """Return full snapshot of the credentials dictionary."""
        with self._lock:
            return copy.deepcopy(self._credentials)


__all__ = ["VaultPreferenceAdapter"]
