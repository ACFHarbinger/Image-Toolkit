import os
import sys

from .paths import BASE_KEYSTORE_FILE, BASE_PEPPER_FILE, BASE_VAULT_FILE, LOCAL_SECRETS_DIR

KEY_ALIAS = "my-aes-key"

ACTIVE_SECRETS_DIR = str(LOCAL_SECRETS_DIR)

def _get_active_path(base_path, suffix=None):
    # `base_path` is used only for its filename shape; vault/keystore/pepper
    # files are always created fresh under ACTIVE_SECRETS_DIR on first use.
    # (No template is seeded from the repo/bundle — real secret material must
    # never ship in an artifact.)
    os.makedirs(ACTIVE_SECRETS_DIR, exist_ok=True)
    filename = os.path.basename(base_path)
    name, ext = os.path.splitext(filename)
    if suffix:
        safe_suffix = "".join(
            c for c in suffix if c.isalnum() or c in ("-", "_", ".")
        ).rstrip()
        if safe_suffix:
            filename = f"{name}-{safe_suffix}{ext}"

    return os.path.join(ACTIVE_SECRETS_DIR, filename)

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
