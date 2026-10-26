# Media loader (`media_loader`)

| Field | Value |
|---|---|
| **Capability ID** | `media_loader` |
| **Service Package** | `middleware/src/services/media_loader/` |
| **Frontend View** | `frontend/src/views/web/MediaLoaderView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/media_loader.json` |
| **Contract SHA-256** | `d6c8697559a419a65d7b053d6cd586cea440d8142070baa6b4282935befeadee` |

## Overview

`media_loader.plan` checks one caller URL and a destination directory. The URL must be http or https, must have a hostname, and must not carry userinfo. The destination must already be a directory. `downloaded` is always false. The call does not fetch the URL.

## Public Surface

- **Python (`middleware/src/services/media_loader/plan.py`):** `plan_download`.
- **Sidecar:** `media_loader.plan`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/media_loader.json`
- **Methods:** `media_loader.plan`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the URL field, destination field, and Plan control are in the tab order.
- **Screen-reader notes & known gaps:** a rejected plan is an alert. The download worker stays on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_media_loader.py -q
```
