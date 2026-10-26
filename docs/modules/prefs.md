# Settings window (`prefs`)

| Field | Value |
|---|---|
| **Capability ID** | `window.settings` |
| **Service Package** | `middleware/src/services/prefs/` |
| **Frontend View** | `frontend/src/views/settings/SettingsWindow.tsx` |
| **Contract Schema** | `contracts/schemas/capability/prefs.json` |
| **Contract SHA-256** | `bcec68d2b7a15845a13d48ab2d1c6bbb077a46b98d3d25bf73822cf17cda1159` |

## Overview

The settings window reads and writes account display, startup profile strings, gallery integers and flags, a logging level plus file-logging flag, and one shortcut override. Values live in a Qt-free JSON document. Shortcut overrides use the existing keybindings file. `prefs.describe` still only lists section names and does not open a store. A new master password is sent to `prefs.set` and is refused unless the current password is passed and a vault session object is injected. There is no second vault, and `auth.status` is not changed. The call does not open the log directory.

## Public Surface

- **Python (`middleware/src/services/prefs/`):** `describe`, `load_window`, `save_window`, `set_master_password`.
- **Sidecar:** `prefs.describe`, `prefs.get`, `prefs.set`, dispatched from `_dispatch_settings`.
- **HostClient:** `prefsDescribe(account)`, `prefsGet(account)`, `prefsSet(params)`.
- **C++ Native Entrypoints:** none. Password changes delegate to an injected session's `update_account_password` or return `C++ vault session locked`.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/prefs.json`
- **Methods:** `prefs.describe`, `prefs.get`, `prefs.set`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** section tabs, fields, Save, and Close are in the tab order. Escape closes the window.
- **Screen-reader notes & known gaps:** the window is a dialog. Account name is read-only. Password fields are absent until a load succeeds. A locked vault session is a status message, not a stored password. Qt groups that are not on this window are recorded as `PARITY-GAP window.settings` in `.agent/reports/parity/window.settings.md`. The migration ledger row stays `pyside-only`.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_prefs.py -q
python middleware/validation/check_docs_freshness.py
```
