# Web Requests Service Module (`web.requests`)

| Field | Value |
|---|---|
| **Capability ID** | `web.requests` |
| **Service Package** | `middleware/src/services/webreq/` |
| **Frontend View** | `frontend/src/views/web/WebRequestsView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/webreq.json` |
| **Contract SHA-256** | `cc77912d431ec19d049e6d3174168873c26a71b938824749d1651c800cdb28b9` |

## Overview

The Web Requests capability (`web.requests`, B-02 #907) provides sequential HTTP request pipeline execution with configurable response actions (logging status codes, headers, response text, and saving binary responses to disk) as well as isolated single-request execution. Backed by native C++ `backend.run_web_requests_sequence` / `WebRequestsLogic` and pure Python fallback execution. Gate B compliant: does not open `cloud_jobs.db` or unsealed databases.

## Public Surface

- **Python Service API (`middleware/src/services/webreq/`):**
  - Commands: `ExecuteCommand`, `SequenceCommand`, `RequestItem`, `ActionItem`
  - Results: `ExecuteResult`, `SequenceResult`, `SequenceItemResult`
  - Coordinator: `WebRequestsService` implementing `WebRequestsServiceProtocol`
- **Sidecar Handlers (`middleware/src/sidecar/handlers/webreq.py`):**
  - `handle_webreq_execute`, `handle_webreq_sequence`
- **HostClient API (`frontend/src/hostclient/client.ts`):**
  - `webreqExecute(params: ExecuteParams): Promise<ExecuteResult>`
  - `webreqSequence(params: SequenceParams): Promise<SequenceResult>`

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/webreq.json` (`cc77912d431ec19d049e6d3174168873c26a71b938824749d1651c800cdb28b9`).
- **Methods (`contracts/methods.toml`):**
  - `webreq.execute`: Executes a single HTTP request with status, header, and body inspection.
  - `webreq.sequence`: Executes a sequential list of HTTP requests with post-response actions.

## Accessibility & Known Gaps

- **Keyboard parity:** URL inputs, method selectors, request/action list controls, and execution buttons are fully keyboard accessible with visible focus rings.
- **Screen-reader notes & known gaps:** Live status announcements for sequence completion and single request status codes.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_webreq_service.py -q
npm run --prefix frontend test -- src/views/web/WebRequestsView.test.tsx
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
```
