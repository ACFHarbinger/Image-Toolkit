# Cloud Jobs window (`cloud.jobs`)

| Field | Value |
|---|---|
| **Capability ID** | `cloud.jobs` |
| **Service Package** | `middleware/src/services/cloud_jobs/` |
| **Frontend View** | `frontend/src/shell/CloudJobsWindow.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_jobs.json` |
| **Contract SHA-256** | `243e17f07c561cb4d0f15da9ef2bc28ebbc570a7bffd9f8e618a6e9f9d758043` |

## Overview

The header has one cloud control. A click shows the labeled `cloud.jobs` window. The gear, or a shift-click, shows the Cloud Compute setup surface. The badge is the running job count and the reserved spend from `cloud_jobs.summary`. The Jobs table and Detail views provide filtering, metrics, timeline, and cancellation. The resources and spend panes project injected rows. The sidecar does not open `cloud_jobs.db`. Terminate does not call a provider.

## Public Surface

- **Python:** `header_badge` and `summary_result` in `badge.py`. `list_jobs` and `job_detail` in `jobs_service.py`. `project_resources`, `project_spend`, and `terminate_result` in `projection.py`.
- **Bridge:** `cloud_jobs.summary`, `cloud_jobs.list`, `cloud_jobs.detail`, `cloud_jobs.resources`, `cloud_jobs.spend`, `cloud_jobs.terminate`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_jobs.json`
- **Methods:** `cloud_jobs.summary`, `cloud_jobs.list`, `cloud_jobs.detail`, `cloud_jobs.resources`, `cloud_jobs.spend`, `cloud_jobs.terminate`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the Cloud Jobs and Cloud Compute buttons are Tab stops. Each orphan's Terminate control is a button.
- **Screen-reader notes & known gaps:** badge and spend changes are not a live region. A refused terminate is a text notice.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_cloud_jobs_badge.py middleware/test/services/test_cloud_jobs_service.py middleware/test/services/test_cloud_jobs_projection.py middleware/test/sidecar/test_server.py -q
```
