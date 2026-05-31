import os
import sys
from .paths import BASE_KEYSTORE_FILE, BASE_VAULT_FILE, BASE_PEPPER_FILE

KEY_ALIAS = "my-aes-key"

# --- Active Dynamic Paths (Mutable) ---
# These are updated at runtime via update_cryptographic_values
KEYSTORE_FILE = BASE_KEYSTORE_FILE
VAULT_FILE = BASE_VAULT_FILE
PEPPER_FILE = BASE_PEPPER_FILE

def _get_suffixed_path(base_path, suffix):
    if not suffix:
        return base_path
    safe_suffix = "".join(
        c for c in suffix if c.isalnum() or c in ("-", "_", ".")
    ).rstrip()
    if not safe_suffix:
        return base_path
    directory, filename = os.path.split(base_path)
    name, ext = os.path.splitext(filename)
    return os.path.join(directory, f"{name}-{safe_suffix}{ext}")

def update_cryptographic_values(account_name):
    global KEYSTORE_FILE, VAULT_FILE, PEPPER_FILE

    print(f"Updating cryptographic paths for account: {account_name}", file=sys.stderr)

    KEYSTORE_FILE = _get_suffixed_path(BASE_KEYSTORE_FILE, account_name)
    VAULT_FILE = _get_suffixed_path(BASE_VAULT_FILE, account_name)
    PEPPER_FILE = _get_suffixed_path(BASE_PEPPER_FILE, account_name)

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
        pkg.KEYSTORE_FILE = KEYSTORE_FILE
        pkg.VAULT_FILE = VAULT_FILE
        pkg.PEPPER_FILE = PEPPER_FILE
