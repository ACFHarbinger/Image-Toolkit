# Cloud Jobs window (`cloud.jobs`)

| Field | Value |
|---|---|
| **Capability ID** | `cloud.jobs` |
| **Service Package** | `middleware/src/services/cloud_jobs/` |
| **Frontend View** | `frontend/src/shell/CloudJobsWindow.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_jobs.json` |
| **Contract SHA-256** | `2f3328bbedb91cf905d6a73fcb17f8e0191d4f0ec5cee0d4e0d4166346b80e00` |

## Overview

The header has one cloud control. A click shows the labeled `cloud.jobs` window. The gear, or a shift-click, shows the Cloud Compute setup surface. The badge is the running job count and the reserved spend from `cloud_jobs.summary`. The resources and spend panes project injected rows. The sidecar does not open `cloud_jobs.db`. Terminate does not call a provider.

## Public Surface

- **Python:** `header_badge` and `summary_result` in `badge.py`. `project_resources`, `project_spend`, and `terminate_result` in `projection.py`.
- **Bridge:** `cloud_jobs.summary`, `cloud_jobs.resources`, `cloud_jobs.spend`, `cloud_jobs.terminate`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_jobs.json`
- **Methods:** `cloud_jobs.summary`, `cloud_jobs.resources`, `cloud_jobs.spend`, `cloud_jobs.terminate`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the Cloud Jobs and Cloud Compute buttons are Tab stops. Each orphan's Terminate control is a button.
- **Screen-reader notes & known gaps:** badge and spend changes are not a live region. A refused terminate is a text notice.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_cloud_jobs_badge.py middleware/test/services/test_cloud_jobs_projection.py middleware/test/sidecar/test_server.py -q
```
