# Image Stitching (`stitch`)

| Field | Value |
|---|---|
| **Capability ID** | `stitch` |
| **Service Package** | `middleware/src/services/stitch/` |
| **Frontend View** | `frontend/src/views/stitch/StitchWorkspace.tsx` |
| **Contract Schema** | `contracts/schemas/capability/stitch.json` |
| **Contract SHA-256** | `8b765179860d10fab062fdc7306e4e53b3a48824e80c816c1aa30bf8e8c0d8e9` |

## Overview

`stitch.status` reports panel state for one of the eight Image Stitching catalog routes. `stitch.run` executes the headless Anime Stitch Pipeline over a frame directory, and `stitch.canvas` computes layout geometry for that directory. The workspace still paints every route as a shared canvas host and does not draw a panorama. Interactive tie-point, seam, and inspector controls stay on PySide6 (`pyside-only`).

## Public Surface

- **Python (`middleware/src/services/stitch/service.py`):** `StitchService` (`get_status`, `run_stitch`, `compute_canvas`). `stitch_status` in `status.py` remains the idle catalog helper.
- **Sidecar:** `stitch.status`, `stitch.run`, and `stitch.canvas` via `_dispatch_system_pages`.
- **HostClient:** `stitchStatus(route)`.
- **C++ Native Entrypoints:** none. The pipeline calls `AnimeStitchPipeline` in `middleware/src/stitching/`.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/stitch.json`
- **Methods:** `stitch.status`, `stitch.run`, `stitch.canvas`
- **Events:** none

Accepted route ids: `stitch.stitch`, `stitch.graph`, `stitch.adjust`, `stitch.canvas`, `stitch.statistics`, `stitch.sequence-builder`, `stitch.hybrid`, `stitch.animation-clusters`. Any other route is an error. `route` is a plain string because those ids contain dots and hyphens.

## Accessibility & Known Gaps

- **Keyboard parity:** the workspace has no controls yet. Route text is a heading.
- **Screen-reader notes & known gaps:** the shared canvas host is a labeled region and is not a live WebGL surface. Alignment, graph editing, and panorama output stay on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider middleware/test/services/test_stitch.py middleware/test/services/test_stitch_service.py -q
```
