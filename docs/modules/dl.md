# Deep Learning (`dl`)

| Field | Value |
|---|---|
| **Capability ID** | `dl` |
| **Service Package** | `middleware/src/services/dl/` |
| **Frontend View** | `frontend/src/views/dl/DlWorkspace.tsx` |
| **Contract Schema** | `contracts/schemas/capability/dl.json` |
| **Contract SHA-256** | `6b83bb886af99c32675010b8ae300c6704ae0d41a3a5f9e8624e80797500dbc8` |

## Overview

`dl.inspect` reads `record.json` and `events.jsonl` from a caller run directory. It does not start a run, write the directory, import torch, or open `library.db`. Training and generation stay on PySide6. `started` is always false.

## Public Surface

- **Python (`middleware/src/services/dl/inspect.py`):** `inspect_run`.
- **Sidecar:** `dl.inspect`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/dl.json`
- **Methods:** `dl.inspect`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the run-directory field and Inspect control are in the tab order.
- **Screen-reader notes & known gaps:** a missing directory or record is the returned reason. Starting a run stays on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_dl_inspect.py -q
```
