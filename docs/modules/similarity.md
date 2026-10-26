# Similarity (`similarity`)

| Field | Value |
|---|---|
| **Capability ID** | `similarity` |
| **Service Package** | `middleware/src/services/similarity/` |
| **Frontend View** | `frontend/src/views/system/SimilarityView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/similarity.json` |
| **Contract SHA-256** | `7103ca769b88b1aee94288b761ff2c647ebbc0f52add99a4b6ed88751cf206a1` |

## Overview

`similarity.compare` reports width, height, and an 8x8 average hash for caller images, plus pairs whose Hamming distance is within the caller's threshold. `similarity.scan` lists pairs in one directory the same way and does not recurse or delete. It does not open `library.db`. Directory deletion stays on PySide6.

## Public Surface

- **Python (`middleware/src/services/similarity/compare.py`):** `compare_paths`, `scan_directory`.
- **Sidecar:** `similarity.compare`, `similarity.scan`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/similarity.json`
- **Methods:** `similarity.compare`, `similarity.scan`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the path list, threshold, and Compare control are in the tab order.
- **Screen-reader notes & known gaps:** a missing file is an error column. Deleting a directory stays on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_similarity.py -q
```
