# Image Stitching (`stitch`)

| Field | Value |
|---|---|
| **Capability ID** | `stitch` |
| **Service Package** | `middleware/src/services/stitch/` |
| **Frontend View** | `frontend/src/views/stitch/StitchWorkspace.tsx` |
| **Contract Schema** | `contracts/schemas/capability/stitch.json` |
| **Contract SHA-256** | `8b765179860d10fab062fdc7306e4e53b3a48824e80c816c1aa30bf8e8c0d8e9` |

## Overview

`stitch.status` reports one of the eight Image Stitching catalog routes and states that the stitch pipeline is not started. The same workspace paints every route. It names the shared canvas host and does not draw a panorama. Nothing here reads images or opens the library store. The PySide6 stitch workspace stays the live surface (`pyside-only`).

## Public Surface

- **Python (`middleware/src/services/stitch/status.py`):** `stitch_status`.
- **Sidecar:** `stitch.status` via `_dispatch_system_pages`.
- **HostClient:** `stitchStatus(route)`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/stitch.json`
- **Methods:** `stitch.status`
- **Events:** none

Accepted route ids: `stitch.stitch`, `stitch.graph`, `stitch.adjust`, `stitch.canvas`, `stitch.statistics`, `stitch.sequence-builder`, `stitch.hybrid`, `stitch.animation-clusters`. Any other route is an error. `route` is a plain string because those ids contain dots and hyphens.

## Accessibility & Known Gaps

- **Keyboard parity:** the workspace has no controls yet. Route text is a heading.
- **Screen-reader notes & known gaps:** the shared canvas host is a labeled region and is not a live WebGL surface. Alignment, graph editing, and panorama output stay on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider middleware/test/services/test_stitch.py -q
```
