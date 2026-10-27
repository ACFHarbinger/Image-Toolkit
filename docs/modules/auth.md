# Authentication (`auth`)

| Field | Value |
|---|---|
| **Capability ID** | `auth` |
| **Service Package** | `middleware/src/services/auth/` |
| **Frontend View** | `frontend/src/components/dialogs/LoginDialog.tsx` |
| **Contract Schema** | `contracts/schemas/capability/auth.json` |
| **Contract SHA-256** | `afff7277b01e3c2ab2b4227c04243622acf37eb6976686fa5624c12b5a46950e` |

## Overview

`auth.unlock` opens the C++ vault session inside the sidecar process and stores the live `VaultManager` on `SidecarServer`. `auth.lock` calls `VaultManager.shutdown` (`backend.vault.lock`) and drops that reference. `auth.status` reports the live session: `unlocked` is a real boolean, and `reason` is `C++ vault session locked` or `C++ vault session open`. The password is a JSON-RPC parameter only. Results do not contain the password, the key, or a session handle. A missing `backend.vault` module returns `success: false` and does not mark the session open. The React login flag is not this session.

## Public Surface

- **Python (`middleware/src/services/auth/`):** `auth_status`, `open_live_session`, `VaultHub`.
- **Sidecar:** `auth.status`, `auth.unlock`, `auth.lock`.
- **HostClient:** `authStatus`, `authUnlock`, `authLock`.
- **C++ Native Entrypoints:** `backend.vault.unlock`, `backend.vault.unlock_raw`, `backend.vault.lock`, `backend.vault.is_unlocked`.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/auth.json`
- **Methods:** `auth.status`, `auth.unlock`, `auth.lock`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the account field, password field, Create Account, and Login are in the tab order. Enter submits login.
- **Screen-reader notes & known gaps:** a failed unlock is an alert. Guest login is not on the sidecar (see `.agent/reports/parity/window.auth.md`). Create-account still uses the existing vault create flow, then `auth.unlock` so the sidecar holds the session.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_auth.py middleware/test/sidecar/test_auth_dispatch.py -q
python middleware/validation/check_docs_freshness.py
```
