# Extractor (`extractor`)

| Field | Value |
|---|---|
| **Capability ID** | `extractor` |
| **Service Package** | `middleware/src/services/extractor/` |
| **Frontend View** | `frontend/src/views/system/ExtractorView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/extractor.json` |
| **Contract SHA-256** | `e1719e97c3a113be36178f4044b9b4aae8c69e8a46503d30ffee61756427461e` |

## Overview

`extractor.probe` reports duration, size, and codec for one caller video path. `extractor.snapshot` and `extractor.extract_range` shell out to ffmpeg when it is on `PATH` and return an error when it is not. `extractor.cut_sheet` crops a still using offset, spacing, and include-partial. Sheet cuts reject more than 1,024 crops before allocating rectangles. Snapshot, range, and sheet extraction return cancellable job IDs; results are read through `jobs.status`. Cancellation stops subsequent crops and preserves crops already published. The calls do not open `library.db`. The player, GIF and MP4 presets, and the overlay canvas stay on PySide6.

## Public Surface

- **Python (`middleware/src/services/extractor/probe.py`, `actions.py`):** `probe_video`, `snapshot_frame`, `extract_range`, `cut_sheet`.
- **Sidecar:** `extractor.probe`, `extractor.snapshot`, `extractor.extract_range`, `extractor.cut_sheet`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/extractor.json`
- **Methods:** `extractor.probe`, `extractor.snapshot`, `extractor.extract_range`, `extractor.cut_sheet`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the path field and Probe control are in the tab order.
- **Screen-reader notes & known gaps:** a missing file or a failed probe is an alert. Frame slicing stays on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_extractor.py -q
```
