# Deep Learning (`dl`)

| Field | Value |
|---|---|
| **Capability ID** | `dl` |
| **Service Package** | `middleware/src/services/dl/` |
| **Frontend View** | `frontend/src/views/dl/DlWorkspace.tsx` |
| **Contract Schema** | `contracts/schemas/capability/dl.json` |
| **Contract SHA-256** | `16c4c2e798bfc498b20a2087e768bb9ed953190d58ce4d78f46a3efa3affee38` |

## Overview

Headless deep learning training, generation, evaluation, inference, and ComfyUI run control (#1111). Provides headless run orchestration, event stream capture, model generation, evaluation scoring, zero-shot inference, and ComfyUI server/queue management behind sidecar methods without Qt or top-level torch/numpy dependencies.

## Public Surface

- **Python (`middleware/src/services/dl/service.py`):** `DeepLearningService`.
- **Python (`middleware/src/services/dl/inspect.py`):** `inspect_run`.
- **Sidecar:** `dl.inspect`, `dl.train`, `dl.status`, `dl.cancel`, `dl.generate`, `dl.evaluate`, `dl.infer`, `dl.comfy_status`, `dl.comfy_start`, `dl.comfy_stop`, `dl.comfy_queue`, `dl.comfy_run_status`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/dl.json`
- **Methods:** `dl.inspect`, `dl.train`, `dl.status`, `dl.cancel`, `dl.generate`, `dl.evaluate`, `dl.infer`, `dl.comfy_status`, `dl.comfy_start`, `dl.comfy_stop`, `dl.comfy_queue`, `dl.comfy_run_status`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the run-directory field and Inspect control are in the tab order.
- **Screen-reader notes & known gaps:** Headless engines and workers operate via sidecar capability methods.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_dl_service.py -q
```
