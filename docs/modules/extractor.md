# Extractor (`extractor`)

| Field | Value |
|---|---|
| **Capability ID** | `extractor` |
| **Service Package** | `middleware/src/services/extractor/` |
| **Frontend View** | `frontend/src/views/system/ExtractorView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/extractor.json` |
| **Contract SHA-256** | `77676457570909d1481fba788b6b0b03abea94398423a03d6e5ba7436bf98562` |

## Overview

`extractor.probe` reports duration, size, and codec for one caller video path. `extractor.snapshot` and `extractor.extract_range` shell out to ffmpeg when it is on `PATH` and return an error when it is not. `extractor.cut_sheet` crops a still using offset, spacing, and include-partial. The calls do not open `library.db`. The player, GIF and MP4 presets, and the overlay canvas stay on PySide6.

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
