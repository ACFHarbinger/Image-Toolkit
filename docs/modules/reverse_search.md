# Reverse image search (`reverse_search`)

| Field | Value |
|---|---|
| **Capability ID** | `reverse_search` |
| **Service Package** | `middleware/src/services/web/reverse_search.py` |
| **Frontend View** | `frontend/src/views/web/ReverseSearch.tsx` |
| **Contract Schema** | `contracts/schemas/capability/reverse_search.json` |
| **Contract SHA-256** | `6150dfc84262f7f243a1dc9ce85ee06f752e46a58a0ae630cb2771e2fad2ae31` |

## Overview

Reverse image search over the existing middleware strategies (B-05 /
#910): the engine catalog mirrors the Qt tab's labels (Google Lens,
TinEye API, Local AI Search, plus the extended SauceNAO / IQDB / Bing /
Yandex engines), and one search run routes onto
`ReverseImageSearchManager`. The engines make live network or browser
calls at the user's request; the bridge carries the commands and this
module never fabricates results. Tests inject fake strategies — no live
HTTP, no Selenium, no provider operations.

## Public Surface

- **Python Service API (`middleware/src/services/web/reverse_search.py`):**
  - `engines_result()` — the SUPPORTED_ENGINES catalog with labels.
  - `search_result(manager, params)` — validates engine/path/ROI/limit,
    runs one manager search, and normalizes the legacy
    `ReverseSearchResult.to_dict` rows (numeric score) into the contract
    payload; provider failures answer `ok: false` with the reason.
- **Bridge:** `reverse_search.engines`, `reverse_search.search`.
- **C++ Native Entrypoints (`import backend`):** the ROI crop
  (`backend.roi.crop_roi`) runs inside the existing manager helper; this
  module adds no new native surface.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/reverse_search.json`
- **Methods (`contracts/methods.toml`):** `reverse_search.engines`, `reverse_search.search`
- **Events (EventHub):** none

## Accessibility & Known Gaps

- **Keyboard parity:** engine select, image path, limit and ROI are
  labeled inputs; Search is a form submit (Enter works); results are a
  text list with the resolution and score spelled out.
- **Screen-reader notes & known gaps:** result rows carry the title (or
  URL) as text with the match quality as a percentage. Result thumbnails
  are not wired yet; the query-image preview is L-01's surface (#895).

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_reverse_search.py middleware/test/sidecar/test_reverse_search_dispatch.py middleware/test/sidecar/test_server.py middleware/test/bridge/test_handshake_schema.py -q
```
