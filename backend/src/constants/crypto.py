import os
import sys
import shutil
from .paths import BASE_KEYSTORE_FILE, BASE_VAULT_FILE, BASE_PEPPER_FILE, LOCAL_SECRETS_DIR

KEY_ALIAS = "my-aes-key"

ACTIVE_SECRETS_DIR = str(LOCAL_SECRETS_DIR)

def _get_active_path(base_path, suffix=None):
    os.makedirs(ACTIVE_SECRETS_DIR, exist_ok=True)
    filename = os.path.basename(base_path)
    name, ext = os.path.splitext(filename)
    if suffix:
        safe_suffix = "".join(
            c for c in suffix if c.isalnum() or c in ("-", "_", ".")
        ).rstrip()
        if safe_suffix:
            filename = f"{name}-{safe_suffix}{ext}"
    
    active_path = os.path.join(ACTIVE_SECRETS_DIR, filename)
    # If the active file does not exist, but the base template file does, copy it!
    if not os.path.exists(active_path) and os.path.exists(base_path):
        try:
            shutil.copy2(base_path, active_path)
            print(f"Copied template {base_path} to {active_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error copying template {base_path} to {active_path}: {e}", file=sys.stderr)
            
    return active_path

# --- Active Dynamic Paths (Mutable) ---
KEYSTORE_FILE = _get_active_path(BASE_KEYSTORE_FILE)
VAULT_FILE = _get_active_path(BASE_VAULT_FILE)
PEPPER_FILE = _get_active_path(BASE_PEPPER_FILE)

def update_cryptographic_values(account_name):
    global KEYSTORE_FILE, VAULT_FILE, PEPPER_FILE

    print(f"Updating cryptographic paths for account: {account_name}", file=sys.stderr)

    KEYSTORE_FILE = _get_active_path(BASE_KEYSTORE_FILE, account_name)
    VAULT_FILE = _get_active_path(BASE_VAULT_FILE, account_name)
    PEPPER_FILE = _get_active_path(BASE_PEPPER_FILE, account_name)

    print("--- CRYPTO PATHS UPDATED ---", file=sys.stderr)
    print(f"KEYSTORE_FILE: {KEYSTORE_FILE}", file=sys.stderr)
    print(f"VAULT_FILE: {VAULT_FILE}", file=sys.stderr)
    print(f"PEPPER_FILE: {PEPPER_FILE}", file=sys.stderr)

    # `backend.src.constants.__init__` copies these names at import time via
    # `from .crypto import *`.  Mutating this module's globals alone is not
    # enough — callers that hold a reference to the *package* (e.g.
    # `import backend.src.constants as udef`) would still see stale values.
    # Sync back through sys.modules to keep every importer consistent.
    pkg = sys.modules.get("backend.src.constants")
    if pkg is not None:
        pkg.KEYSTORE_FILE = KEYSTORE_FILE # pyrefly: ignore [missing-attribute]
        pkg.VAULT_FILE = VAULT_FILE # pyrefly: ignore [missing-attribute]
        pkg.PEPPER_FILE = PEPPER_FILE # pyrefly: ignore [missing-attribute]
