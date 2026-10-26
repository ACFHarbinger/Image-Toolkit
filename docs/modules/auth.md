# Authentication (`auth`)

| Field | Value |
|---|---|
| **Capability ID** | `auth` |
| **Service Package** | `middleware/src/services/auth/` |
| **Frontend View** | `frontend/src/components/dialogs/LoginDialog.tsx` |
| **Contract Schema** | `contracts/schemas/capability/auth.json` |
| **Contract SHA-256** | `45ba90b445e7680a81ad6faf66fe865527dd8ae926f5b5408067ce9d12afc231` |

## Overview

`auth.status` reports that the webview session stays locked. `unlocked` is always false. The call does not read or write a vault file, does not open `library.db` or `cloud_jobs.db`, and does not take a password. Unlock stays on the C++ session. The PySide6 authentication window is unchanged.

## Public Surface

- **Python (`middleware/src/services/auth/status.py`):** `auth_status`.
- **Sidecar:** `auth.status`.
- **HostClient:** `authStatus({ account })`.
- **C++ Native Entrypoints:** none. The webview does not unlock the vault.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/auth.json`
- **Methods:** `auth.status`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the account field, password field (not sent), Create Account, and Login are in the tab order. Enter reports the locked status.
- **Screen-reader notes & known gaps:** the locked reason is an alert. Account creation does not succeed. Vault unlock stays on the C++ session.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_auth.py middleware/test/sidecar/test_auth_dispatch.py -q
python middleware/validation/check_docs_freshness.py
```
