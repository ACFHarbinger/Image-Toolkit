# Cloud Jobs window (`cloud.jobs`)

| Field | Value |
|---|---|
| **Capability ID** | `cloud.jobs` |
| **Service Package** | `middleware/src/services/cloud_jobs/` |
| **Frontend View** | `frontend/src/shell/CloudJobsWindow.tsx` |
| **Contract Schema** | `contracts/schemas/capability/cloud_jobs.json` |
| **Contract SHA-256** | `4c81075644506a81723408ead2ecfb93737893c4c613aa493daf80ff9e4dcb65` |

## Overview

The header has one cloud control. A click shows the labeled `cloud.jobs` window. The gear, or a shift-click, shows the Cloud Compute setup surface. The badge is the running job count and the reserved spend from `cloud_jobs.summary`. The Jobs table and Detail views provide filtering, metrics, timeline, and cancellation (#848).

## Public Surface

- **Python Service API (`middleware/src/services/cloud_jobs/`):**
  - `header_badge(rows)` returns `(running, reserved_usd)` from `(state, reserved_usd)` pairs.
  - `summary_result(rows)` is the bridge payload. `None` means no projection is attached.
  - `list_jobs(jobs_data, params)` lists and filters jobs.
  - `job_detail(jobs_data, params)` returns detailed metrics, spend, timeline, and status.
- **C++ Native Entrypoints (`import backend`):** none. The sealed store is not opened here.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/cloud_jobs.json`
- **Methods (`contracts/methods.toml`):** `cloud_jobs.summary`, `cloud_jobs.list`, `cloud_jobs.detail`
- **Events (EventHub):** none

## Accessibility & Known Gaps

- **Keyboard parity:** the Cloud Jobs and Cloud Compute buttons are Tab stops. Enter activates them. Shift-click is a pointer shortcut; the gear is the keyboard path to Cloud Compute.
- **Screen-reader notes & known gaps:** the badge text is inside the Cloud Jobs button name's sibling, so the count is visible text. A live region for badge changes is not announced yet.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_cloud_jobs_service.py middleware/test/sidecar/test_server.py middleware/test/bridge/test_handshake_schema.py -q
```
