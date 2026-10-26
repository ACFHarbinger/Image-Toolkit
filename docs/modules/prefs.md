# Settings window (`prefs`)

| Field | Value |
|---|---|
| **Capability ID** | `window.settings` |
| **Service Package** | `middleware/src/services/prefs/` |
| **Frontend View** | `frontend/src/views/settings/SettingsWindow.tsx` |
| **Contract Schema** | `contracts/schemas/capability/prefs.json` |
| **Contract SHA-256** | `b7cc81172a18224dea0756cc71bbabbb7f948dabf1c51f360ae906c4e1ce68ec` |

## Overview

`prefs.describe` lists the six settings-window sections for a non-empty account. Credentials stay on the C++ vault session: the call does not open `VaultManager`, `~/.image-toolkit`, or a database, and it does not change a password. The key-value `settings` capability is a different contract.

## Public Surface

- **Python (`middleware/src/services/prefs/describe.py`):** `describe`.
- **Sidecar:** `prefs.describe`, dispatched from `_dispatch_settings`.
- **HostClient:** `prefsDescribe(account)`.
- **C++ Native Entrypoints:** none. The Rust `load_user_settings`, `save_user_settings`, and `update_master_password` commands are removed.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/prefs.json`
- **Methods:** `prefs.describe`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** section tabs and Close are in the tab order. Escape closes the window.
- **Screen-reader notes & known gaps:** the window is a dialog. Credentials and reset show why a password is not collected and have no password field. Appearance, profiles, shortcuts, and tab config do not write the vault yet.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_prefs.py -q
python middleware/validation/check_docs_freshness.py
```
