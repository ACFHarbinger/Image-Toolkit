# Desk (`desk`)

| Field | Value |
|---|---|
| **Capability ID** | `window.logging` |
| **Service Package** | `middleware/src/services/desk/` |
| **Frontend View** | `frontend/src/views/windows/LogDeskView.tsx`, `frontend/src/views/windows/MetadataDeskView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/desk.json` |
| **Contract SHA-256** | `046cd3b8af443f21273cad9ce9a9c12ba23e6c943ff9ed065c97f3f61e323af4` |

## Overview

`logs.read` returns the last lines of one caller log and does not follow the file. `metadata.describe` reports the basename, size, and suffix of one caller file. Neither call opens `library.db`, writes the path, or decodes image pixels. The PySide6 logging and metadata windows stay in place.

Open **Developer / Diagnostics → Logs** or **File Metadata** from the shell rail. Both pages use the shell’s transport-backed HostClient.

## Public Surface

- **Python (`middleware/src/services/desk/logs.py`):** `read_log`.
- **Python (`middleware/src/services/desk/metadata.py`):** `describe_file`.
- **Sidecar:** `logs.read`, `metadata.describe`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/desk.json`
- **Methods:** `logs.read`, `metadata.describe`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the path field, the log limit, and the submit control are in the tab order.
- **Screen-reader notes & known gaps:** a bridge failure is an alert. The reason is plain text. Live tail and metadata editing stay on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_desk.py middleware/test/sidecar/test_desk_dispatch.py -q
```
