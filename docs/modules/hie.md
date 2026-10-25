# Hybrid Image Editor (HIE) Service Module (`services/hie`)

| Field | Value |
|---|---|
| **Capability ID** | `editor.hybrid` |
| **Service Package** | `middleware/src/services/hie/service.py` |
| **Frontend View** | `submodules/HIE/gui/src/hie_tab.py` (migrating to Wave 8 #915 E-02 `frontend/src/tabs/editor/`) |
| **Contract Schema** | `contracts/CONTRACTS.sha256` |
| **Contract SHA-256** | `48148467512ee584ac757ff420b1212bf259e6bc06655926b2980419a7ded0cc` |

## Overview

The Hybrid Image Editor (HIE) provides a non-destructive multi-layer document model, render-graph pipeline, and neural restoration tools (watermark removal, inpainting, super-resolution, tone balancing, and smart brush assistance). Backed by C++ exact dynamic programming and graph-cut solvers in `backend/` and Python pipeline orchestration in `submodules/HIE/middleware/src/`, it handles media loading, timeline manipulation, and policy-driven proposals. Absorbed in W0-03 (#867 Phase C) and unblocking Wave 8 editor #915 (E-02).

## Public Surface

- **Python Service API (`middleware/src/services/hie/`):**
  - Commands: `HieOpenDocumentCommand`, `HieEditCommand`, `HieExportDocumentCommand`, `HieListCapabilitiesCommand`
  - Results: `HieOpenDocumentResult`, `HieEditResult`, `HieExportDocumentResult`, `HieListCapabilitiesResult`
  - Handlers & Service: `HieService`, `HieServiceProtocol`
- **Core Entities:** `Document`, `Layer`, `Modifier`, `Mask`, `FrameSequence` (`submodules/HIE/middleware/src/document.py`), `IpcService` (`submodules/HIE/middleware/src/ipc_service.py`).

## Contract & Routing

- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`48148467512ee584ac757ff420b1212bf259e6bc06655926b2980419a7ded0cc`).
- **Feature Ledger Routing:** Tracks feature row `editor.hybrid` (Issue #915, wave-8) with routes `editor.hybrid` and route map `{ hie_editor = "editor.hybrid" }`.
- **Boundary Enforcement:**
  - `import-linter` contracts in `pyproject.toml` (`middleware.src.services must not import GUI`, `middleware.src.services must not import PySide`, `middleware.src.services features must be independent`).

## Accessibility & Known Gaps

- **Keyboard navigation:** Layer selection, modifier toggling, and parameter adjustments are keyboard accessible via Tab and Arrow keys.
- **Screen-reader notes & known gaps:** Real-time canvas editing provides live polite announcements for layer reordering and filter application. Full WebGL viewport accessibility cutover is scheduled in Wave 8 #915.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_hie_service.py -v
lint-imports
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
```
