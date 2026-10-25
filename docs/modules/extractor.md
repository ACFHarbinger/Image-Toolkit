# Extractor (`extractor`)

| Field | Value |
|---|---|
| **Capability ID** | `extractor` |
| **Service Package** | `middleware/src/services/extractor/` |
| **Frontend View** | `frontend/src/views/system/ExtractorView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/extractor.json` |
| **Contract SHA-256** | `5f01eac1cb76554610fa972abdedf2212bdf9d973c43fbe9c6e21307c16f4567` |

## Overview

`extractor.probe` reports duration, size, and codec for one caller video path. ffprobe is run with an argument list. The call does not open `library.db` and does not extract frames. Frame extraction and the frame-slice canvas stay on PySide6. The Rust `video_commands` module is removed because the webview does not call it.

## Public Surface

- **Python (`middleware/src/services/extractor/probe.py`):** `probe_video`.
- **Sidecar:** `extractor.probe`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/extractor.json`
- **Methods:** `extractor.probe`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the path field and Probe control are in the tab order.
- **Screen-reader notes & known gaps:** a missing file or a failed probe is an alert. Frame slicing stays on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_extractor.py -q
```
