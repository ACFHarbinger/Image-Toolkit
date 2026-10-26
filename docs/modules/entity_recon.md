# Entity reconnaissance and provenance (`entity_recon`)

| Field | Value |
|---|---|
| **Capability ID** | `entity_recon` |
| **Service Package** | `middleware/src/services/web/entity_recon.py` |
| **Frontend View** | `frontend/src/views/web/EntityRecon.tsx` |
| **Contract Schema** | `contracts/schemas/capability/entity_recon.json` |
| **Contract SHA-256** | `a08755e4e01024caad75f6a045a94c22f359c962d2ca4a6211587c0c1a0f80de` |

## Overview

Entity reconnaissance over the recon engine (B-06 / #911): one cutout
resolves to an identity with a full provenance report — local dataset
matches (ArcFace/CLIP embeddings) first, with reverse-image web
discovery only at the user's explicit request (`search_scope`
`web`/`both`); the default scope is fully offline. The engine (dataset
index and web dispatcher) is injected into the sidecar; with none
attached every result stays `available: false` and the view says so
instead of inventing an identity.

## Public Surface

- **Python Service API (`middleware/src/services/web/entity_recon.py`):**
  - `describe_result(engine)` — the `ReconConfig` snapshot and
    engine-attached state.
  - `resolve_result(engine, cutout_rgb, cutout_png, params)` — applies the
    caller's validated scope/threshold/top-k overrides (privacy derived
    from the scope), runs one resolution, and normalizes
    `IdentityResolution` plus the provenance report into the contract
    payload; unreadable images and engine failures answer failed
    resolves, not bridge errors.
- **Bridge:** `entity_recon.describe`, `entity_recon.resolve`.
- **C++ Native Entrypoints (`import backend`):** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/entity_recon.json`
- **Methods (`contracts/methods.toml`):** `entity_recon.describe`, `entity_recon.resolve`
- **Events (EventHub):** none

## Accessibility & Known Gaps

- **Keyboard parity:** cutout path, scope, threshold and top-k are
  labeled inputs; Resolve is a form submit (Enter works); Export
  provenance is a button.
- **Screen-reader notes & known gaps:** the summary states the name,
  confidence percentage and method as text; provenance entries list
  kind, domain and label. The cutout image preview is L-01's surface
  (#895); dataset indexing and batch building stay on the worker
  lifecycle and are not bridge methods yet.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_entity_recon.py middleware/test/sidecar/test_entity_recon_dispatch.py middleware/test/sidecar/test_server.py middleware/test/bridge/test_handshake_schema.py -q
```
