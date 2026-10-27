# Cloud sync (`drive_sync`)

| Field | Value |
|---|---|
| **Capability ID** | `drive_sync` |
| **Service Package** | `middleware/src/services/drive_sync/` |
| **Frontend View** | `frontend/src/views/web/DriveSyncView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/drive_sync.json` |
| **Contract SHA-256** | `87f8297faa7efd0c5d5028cd8d14b7c1cfa9c23a9968dab7d7d4172f2afc9b95` |

## Overview

`drive_sync.plan` records a provider (`google_drive`, `dropbox`, or `onedrive`) and 1–32 caller paths. `submitted` is always false. The call does not authenticate, upload, stat the paths, or open `cloud_jobs.db`. The path cap is enforced in Python because the runtime schema subset has no `minItems`.

## Public Surface

- **Python (`middleware/src/services/drive_sync/plan.py`):** `plan_sync`.
- **Sidecar:** `drive_sync.plan`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/drive_sync.json`
- **Methods:** `drive_sync.plan`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the provider selector, path field, and Plan control are in the tab order.
- **Screen-reader notes & known gaps:** a rejected plan is an alert. Provider login and the upload itself stay on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_drive_sync.py -q
```
