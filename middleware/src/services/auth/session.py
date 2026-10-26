"""Unlock or create an account vault. Credentials arrive on stdin, never on argv."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Any

import middleware.src.constants as udef
from middleware.src.core.vault_manager import CryptographyLibNotBuiltError, VaultManager


class VaultOpenError(Exception):
    """Unlock failed. The message is safe to return: it never includes the password or key."""


class LiveVault:
    """VaultManager kept open for the sidecar process. shutdown locks the C++ session."""

    def __init__(self, account: str, manager: VaultManager, profiles: list[str]) -> None:
        self.account = account
        self.open = True
        self.profiles = profiles
        self._manager = manager

    def shutdown(self) -> None:
        if not self.open:
            return
        self._manager.shutdown()
        self.open = False


def _require(account: str, password: str) -> tuple[str, str]:
    cleaned = account.strip()
    if not cleaned:
        raise ValueError("account is empty")
    if not password:
        raise ValueError("password is empty")
    return cleaned, password


def _load_vault_api() -> Any | None:
    """Return backend.vault, or None when the native module is not importable."""
    try:
        import backend.vault as vault_api
    except ImportError:
        return None
    if not all(hasattr(vault_api, name) for name in ("unlock", "unlock_raw", "lock", "is_unlocked")):
        return None
    return vault_api


def open_live_session(account: str, password: str) -> LiveVault:
    """Unlock in-process and return the live manager. Does not shut the session down."""
    cleaned, raw_password = _require(account, password)
    api = _load_vault_api()
    if api is None:
        raise VaultOpenError("C++ vault module is missing.")
    udef.update_cryptographic_values(cleaned)
    manager: VaultManager | None = None
    try:
        manager = VaultManager()
        manager.load_keystore(udef.KEYSTORE_FILE, raw_password)
        manager.get_secret_key(udef.KEY_ALIAS, raw_password)
        manager.init_vault(udef.VAULT_FILE)
        stored = manager.load_account_credentials()
        if stored.get("account_name") != cleaned:
            raise VaultOpenError("Account name does not match the stored account.")
        salt = stored.get("salt") or ""
        expected = stored.get("hashed_password")
        digest = hashlib.sha256((raw_password + salt + manager.PEPPER).encode("utf-8")).hexdigest()
        if digest != expected:
            raise VaultOpenError("Invalid password.")
        handle = getattr(manager, "_session_handle", None)
        if not handle or not api.is_unlocked(handle):
            raise VaultOpenError("C++ vault session was not opened.")
        profiles = list((stored.get("system_preference_profiles") or {}).keys())
        return LiveVault(cleaned, manager, profiles)
    except VaultOpenError:
        if manager is not None:
            manager.shutdown()
        raise
    except FileNotFoundError:
        if manager is not None:
            manager.shutdown()
        raise VaultOpenError("Account files not found. Does this account exist?") from None
    except CryptographyLibNotBuiltError:
        if manager is not None:
            manager.shutdown()
        raise VaultOpenError("C++ vault module is missing.") from None
    except Exception:
        if manager is not None:
            manager.shutdown()
        raise VaultOpenError("C++ vault session was not opened.") from None


def unlock(account: str, password: str) -> dict[str, Any]:
    """One-shot CLI unlock. The process that calls this shuts the session down before returning."""
    try:
        live = open_live_session(account, password)
    except VaultOpenError as exc:
        return {"success": False, "message": str(exc)}
    profiles = list(live.profiles)
    message = f"Login successful for {live.account}."
    live.shutdown()
    return {"success": True, "message": message, "profiles": profiles}


def create_account(account: str, password: str) -> dict[str, Any]:
    cleaned, raw_password = _require(account, password)
    udef.update_cryptographic_values(cleaned)
    if os.path.exists(udef.KEYSTORE_FILE) or os.path.exists(udef.VAULT_FILE):
        return {"success": False, "message": "An account with that name already exists. Log in instead."}
    manager: VaultManager | None = None
    try:
        manager = VaultManager()
        manager.create_key_if_missing(udef.KEY_ALIAS, udef.KEYSTORE_FILE, raw_password)
        manager.get_secret_key(udef.KEY_ALIAS, raw_password)
        manager.init_vault(udef.VAULT_FILE)
        manager.save_account_credentials(cleaned, raw_password)
        return {"success": True, "message": f"Account '{cleaned}' created."}
    except CryptographyLibNotBuiltError as exc:
        return {"success": False, "message": str(exc)}
    finally:
        if manager is not None:
            manager.shutdown()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        json.dump({"success": False, "message": "Invalid login request."}, sys.stdout)
        return 0
    action = payload.get("action")
    account = str(payload.get("account") or "")
    password = str(payload.get("password") or "")
    try:
        if action == "login":
            result = unlock(account, password)
        elif action == "create":
            result = create_account(account, password)
        else:
            result = {"success": False, "message": "Unknown action."}
    except ValueError as exc:
        result = {"success": False, "message": str(exc)}
    except Exception as exc:
        message = str(exc) or "Login failed."
        if password:
            message = message.replace(password, "********")
        result = {"success": False, "message": message}
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
