"""`update-settings` command: bulk find/replace across the secure vault and
QSettings without launching the GUI."""

from __future__ import annotations

import getpass
import hashlib
import json
import re
import sys

from PySide6.QtCore import QSettings

import backend.src.constants as udef
from backend.src.core.vault_manager import VaultManager


def _recursive_replace(val, search: str, replace: str, use_regex: bool):
    """Apply search/replace to every string leaf in a str/dict/list value;
    return (new_val, replacement_count)."""
    local_count = 0
    if isinstance(val, str):
        if use_regex:
            try:
                new_val, count = re.subn(search, replace, val)
                return new_val, count
            except Exception:
                new_val = val.replace(search, replace)
                count = val.count(search)
                return new_val, count
        else:
            new_val = val.replace(search, replace)
            count = val.count(search)
            return new_val, count
    elif isinstance(val, dict):
        new_dict = {}
        for k, v in val.items():
            new_v, count = _recursive_replace(v, search, replace, use_regex)
            new_dict[k] = new_v
            local_count += count
        return new_dict, local_count
    elif isinstance(val, list):
        new_list = []
        for item in val:
            new_item, count = _recursive_replace(item, search, replace, use_regex)
            new_list.append(new_item)
            local_count += count
        return new_list, local_count
    return val, 0


def dispatch_update_settings(args: dict) -> None:
    search = args.get("search")
    replace = args.get("replace")
    use_regex = args.get("regex", False)
    account = args.get("account", "a")
    password = args.get("password")

    if not search:
        print("❌ Error: --search pattern is required.", file=sys.stderr)
        return

    # Update cryptographic paths for the specified account
    udef.update_cryptographic_values(account)

    if not password:
        password = getpass.getpass(prompt=f"Enter Master Password for account '{account}': ")

    print(f"🔒 Initializing secure vault for account '{account}'...")
    try:
        vault_manager = VaultManager()
        vault_manager.load_keystore(udef.KEYSTORE_FILE, password)
        vault_manager.get_secret_key(udef.KEY_ALIAS, password)
        vault_manager.init_vault(udef.VAULT_FILE)
        stored_data = vault_manager.load_account_credentials()
    except Exception as e:
        print(f"❌ Failed to load secure vault: {e}", file=sys.stderr)
        return

    # Verify password hash
    stored_hash = stored_data.get("hashed_password")
    stored_salt = stored_data.get("salt")
    pepper = vault_manager.PEPPER
    password_combined = (password + stored_salt + pepper).encode("utf-8")
    verification_hash = hashlib.sha256(password_combined).hexdigest()
    if verification_hash != stored_hash:
        print("❌ Error: Invalid password.", file=sys.stderr)
        return

    print("✅ Vault unlocked successfully.")

    # 1. Update Vault
    updated_data, vault_count = _recursive_replace(stored_data, search, replace, use_regex)
    if vault_count > 0:
        try:
            vault_manager.save_data(json.dumps(updated_data))
            print(f"✅ Updated {vault_count} values/fields in the Secure Vault.")
        except Exception as e:
            print(f"❌ Failed to save updated vault data: {e}", file=sys.stderr)
            return
    else:
        print("ℹ️ No matching fields found in Secure Vault.")

    # 2. Update QSettings
    qsettings_count = 0
    try:
        qsettings = QSettings("ImageToolkit", "ImageToolkit")
        for key in qsettings.allKeys():
            val = qsettings.value(key)
            if isinstance(val, (str, list, dict)):
                new_val, count = _recursive_replace(val, search, replace, use_regex)
                if count > 0:
                    qsettings.setValue(key, new_val)
                    qsettings_count += count
        if qsettings_count > 0:
            print(f"✅ Updated {qsettings_count} values/fields in QSettings.")
        else:
            print("ℹ️ No matching fields found in QSettings.")
    except Exception as e:
        print(f"❌ Failed to update QSettings: {e}", file=sys.stderr)
        return

    try:
        vault_manager.shutdown()
    except Exception:
        pass

    print("🎉 Settings bulk pattern update completed successfully!")
