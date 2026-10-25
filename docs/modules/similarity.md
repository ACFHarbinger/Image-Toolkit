# Similarity (`similarity`)

| Field | Value |
|---|---|
| **Capability ID** | `similarity` |
| **Service Package** | `middleware/src/services/similarity/` |
| **Frontend View** | `frontend/src/views/system/SimilarityView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/similarity.json` |
| **Contract SHA-256** | `57cbae48dcdc65e25a8412c734e890602432fa92f2c57600fe28ec4c6b825408` |

## Overview

`similarity.compare` reports width, height, and an 8x8 average hash for caller images, plus pairs whose Hamming distance is within the caller's threshold. It does not open `library.db` and it does not delete files. Directory deletion stays on PySide6.

## Public Surface

- **Python (`middleware/src/services/similarity/compare.py`):** `compare_paths`.
- **Sidecar:** `similarity.compare`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/similarity.json`
- **Methods:** `similarity.compare`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the path list, threshold, and Compare control are in the tab order.
- **Screen-reader notes & known gaps:** a missing file is an error column. Deleting a directory stays on PySide6.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_similarity.py -q
```
