# Merge (`merge`)

| Field | Value |
|---|---|
| **Capability ID** | `merge` |
| **Service Package** | `middleware/src/services/merge/` |
| **Frontend View** | `frontend/src/views/system/MergeView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/merge.json` |
| **Contract SHA-256** | `4d371e905879d266771d27d557b42b828bc5b8084838565b350b6941532e33df` |

## Overview

`merge.concatenate` joins two to eight caller images horizontally or vertically and writes a PNG or JPEG at a caller path. `merge.place` paints caller rectangles (x, y, width, height) with Pillow and reports width, height, and the written path. Header size is checked before decode. A canvas larger than four million pixels is refused. Grid, panorama, and the external stitch engines stay on PySide6. Nothing here opens `library.db`.

## Public Surface

- **Python (`middleware/src/services/merge/concatenate.py`, `placement.py`):** `concatenate`, `place`.
- **Sidecar:** `merge.concatenate`, `merge.place`.
- **C++ Native Entrypoints:** none. The Rust `merge_images` command is removed.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/merge.json`
- **Methods:** `merge.concatenate`, `merge.place`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the path list, output path, direction, spacing, align, and Concatenate control are in the tab order.
- **Screen-reader notes & known gaps:** a refusal is an alert. Dragging images on a canvas stays on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_merge.py -q
```
