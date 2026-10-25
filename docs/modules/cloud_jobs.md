# Cloud Jobs window and submit surfaces (`cloud.jobs`)

| Field | Value |
|---|---|
| **Capability ID** | `cloud.jobs` |
| **Service Package** | `middleware/src/services/cloud_jobs/` / `middleware/src/cloud/service.py` |
| **Frontend View** | `frontend/src/views/cloudjobs/RequestBuilder.tsx` / `frontend/src/shell/CloudJobsWindow.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_jobs.json` |
| **Contract SHA-256** | `3618ba3d7ef091de6198fb507c1f5f7557db4494c4c6a1ab960a6f1fd1bee37c` |

## Overview

The header has one cloud control. A click shows the labeled `cloud.jobs` window. The gear, or a shift-click, shows the Cloud Compute setup surface. The badge is the running job count and the reserved spend from `cloud_jobs.summary`. The Jobs table and Detail views provide filtering, metrics, timeline, and cancellation (#848). `cloud_jobs.preview` returns the Plan & cost sheet from `CloudJobService.preview`. `cloud_jobs.submit` sends that spec with the acknowledgements the sheet collected. When the sidecar has no service attached, the calls stay unavailable and the sheet does not invent a price or report a dispatch.

## Public Surface

- **Python Service API (`middleware/src/services/cloud_jobs/`):**
  - `header_badge(rows)` returns `(running, reserved_usd)` from `(state, reserved_usd)` pairs.
  - `summary_result(rows)` is the bridge payload. `None` means no projection is attached.
  - `list_jobs(jobs_data, params)` lists and filters jobs.
  - `job_detail(jobs_data, params)` returns detailed metrics, spend, timeline, and status.
- **Python Service API (`middleware/src/cloud/service.py`):** `CloudJobService.preview` and `CloudJobService.submit`.
- **Bridge:** `cloud_jobs.summary`, `cloud_jobs.list`, `cloud_jobs.detail`, `cloud_jobs.preview`, `cloud_jobs.submit`.
- **C++ Native Entrypoints (`import backend`):** none. The sealed store is not opened here.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_jobs.json`
- **Methods (`contracts/methods.toml`):** `cloud_jobs.summary`, `cloud_jobs.list`, `cloud_jobs.detail`, `cloud_jobs.preview`, `cloud_jobs.submit`
- **Events (EventHub):** none

## Accessibility & Known Gaps

- **Keyboard parity:** the execution-mode selector stays enabled; only unsupported options are disabled. Confirm is a button. The Cloud Jobs and Cloud Compute buttons are Tab stops. Enter activates them.
- **Screen-reader notes & known gaps:** the badge text is inside the Cloud Jobs button name's sibling, so the count is visible text. A live region for badge changes is not announced yet. Unknown pricing and an unavailable submission are text notices.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_cloud_jobs_badge.py middleware/test/services/test_cloud_jobs_service.py middleware/test/sidecar/test_server.py middleware/test/bridge/test_handshake_schema.py middleware/test/cloud/test_cloud_jobs_submit_surfaces.py -q
```
