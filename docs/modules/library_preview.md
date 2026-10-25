# Library preview (`library_preview`)

| Field | Value |
|---|---|
| **Capability ID** | `library_preview` |
| **Service Package** | `middleware/src/services/library_preview/` |
| **Frontend View** | `frontend/src/views/library/LibraryPreviewWindow.tsx` |
| **Contract Schema** | `contracts/schemas/capability/library_preview.json` |
| **Contract SHA-256** | `ce9a0bef6eafb08082f4bf9753f73870686ceabbfc9c5b79f23a654e13ece677` |

## Overview

The #895 preview pop-out. `describe` reports size and whether a file is animated. `frame` returns the first frame as a PNG whose longest edge is at most 512, because the webview asset scope does not include arbitrary originals. `difference` returns an absolute RGB map for two same-size images and refuses a size mismatch instead of resizing. Nothing here opens `library.db`. Drag into and out of the webview stays on spike S-05.

## Public Surface

- **Python (`middleware/src/services/library_preview/preview.py`):** `describe_paths`, `frame_png`, `difference_map`.
- **Sidecar:** `library_preview.describe`, `library_preview.frame`, `library_preview.difference`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/library_preview.json`
- **Methods:** `library_preview.describe`, `library_preview.frame`, `library_preview.difference`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** path list, Inspect, mode buttons, previous, next, zoom, rotate, overlay slider, and Difference are buttons or fields in the tab order.
- **Screen-reader notes & known gaps:** a missing file is an alert. GIF playback is the first frame only. The drag preview is visual and does not take pointer events. OS drag-in and drag-out is still unchecked.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_library_preview.py -q
```
