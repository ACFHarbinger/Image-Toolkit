# Cloud Jobs resources and spend

| Field | Value |
|---|---|
| **Capability ID** | `cloud.jobs` |
| **Service Package** | `middleware/src/services/cloud_jobs/` |
| **Frontend View** | `frontend/src/shell/CloudJobsViews.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_jobs.json` |
| **Contract SHA-256** | `383c9796d778174fdd8d7107f560a7a5320fdfd8fb60d72a5fdc6e9d33cf7426` |

## Overview

The `cloud.jobs` window lists tagged resources, marks orphans, and draws spend from ledger rows. The sidecar projects rows it is given. It does not open `cloud_jobs.db`. Terminate does not call a provider.

## Public Surface

- **Python:** `project_resources`, `project_spend`, and `terminate_result` in `middleware/src/services/cloud_jobs/projection.py`.
- **Bridge:** `cloud_jobs.resources`, `cloud_jobs.spend`, `cloud_jobs.terminate`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_jobs.json`
- **Methods:** `cloud_jobs.resources`, `cloud_jobs.spend`, `cloud_jobs.terminate`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** each orphan's Terminate control is a button. Spend is text.
- **Screen-reader notes & known gaps:** spend changes are not a live region. A refused terminate is a text notice.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_cloud_jobs_projection.py middleware/test/sidecar/test_server.py -q
```
