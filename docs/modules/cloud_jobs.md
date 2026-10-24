# Cloud Jobs preview and submit

| Field | Value |
|---|---|
| **Capability ID** | `cloud_jobs` |
| **Service Package** | `middleware/src/cloud/service.py` |
| **Frontend View** | `frontend/src/views/cloudjobs/PlanCostSheet.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_jobs.json` |
| **Contract SHA-256** | `b6dc9ff2d559c64a7c8d3ca721387a0575852a82848a6734bb20f7ec1bdcc30a` |

## Overview

`cloud_jobs.preview` returns the Plan & cost sheet from `CloudJobService.preview`. `cloud_jobs.submit` sends that spec with the acknowledgements the sheet collected. When the sidecar has no service, both calls stay unavailable and the sheet does not invent a price or report a dispatch.

## Public Surface

- **Python:** `CloudJobService.preview` and `CloudJobService.submit`.
- **Bridge:** `cloud_jobs.preview`, `cloud_jobs.submit`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_jobs.json`
- **Methods:** `cloud_jobs.preview`, `cloud_jobs.submit`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the execution-mode selector stays enabled. Only the unsupported managed-batch option is disabled. Confirm is a button.
- **Screen-reader notes & known gaps:** unknown pricing and an unavailable submission are text notices. They are not live regions.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/sidecar/test_server.py -q
```
