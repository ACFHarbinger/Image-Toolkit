# Hybrid Image Editor (HIE) Service Module (`services/hie`)

| Field | Value |
|---|---|
| **Capability ID** | `editor.hybrid` |
| **Service Package** | `middleware/src/services/hie/service.py` |
| **Frontend View** | `submodules/HIE/gui/src/hie_tab.py` (migrating to Wave 8 #915 E-02 `frontend/src/tabs/editor/`) |
| **Contract Schema** | `contracts/CONTRACTS.sha256` |
| **Contract SHA-256** | `fa9e3693e2291ced0dfb8ea17a7f05e5e7d4db54a64c8886140409356df48860` |

## Overview

The Hybrid Image Editor (HIE) provides a non-destructive multi-layer document model, render-graph pipeline, and neural restoration tools (watermark removal, inpainting, super-resolution, tone balancing, and smart brush assistance). Backed by C++ exact dynamic programming and graph-cut solvers in `backend/` and Python pipeline orchestration in `submodules/HIE/middleware/src/`, it handles media loading, timeline manipulation, and policy-driven proposals. Absorbed in W0-03 (#867 Phase C) and unblocking Wave 8 editor #915 (E-02).

## Public Surface

- **Python Service API (`middleware/src/services/hie/`):**
  - Commands: `HieOpenDocumentCommand`, `HieEditCommand`, `HieExportDocumentCommand`, `HieListCapabilitiesCommand`
  - Results: `HieOpenDocumentResult`, `HieEditResult`, `HieExportDocumentResult`, `HieListCapabilitiesResult`
  - Handlers & Service: `HieService`, `HieServiceProtocol`
- **Core Entities:** `Document`, `Layer`, `Modifier`, `Mask`, `FrameSequence` (`submodules/HIE/middleware/src/document.py`), `IpcService` (`submodules/HIE/middleware/src/ipc_service.py`).

## Contract & Routing

- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`fa9e3693e2291ced0dfb8ea17a7f05e5e7d4db54a64c8886140409356df48860`).
- **Feature Ledger Routing:** Tracks feature row `editor.hybrid` (Issue #915, wave-8) with routes `editor.hybrid` and route map `{ hie_editor = "editor.hybrid" }`.
- **Boundary Enforcement:**
  - `import-linter` contracts in `pyproject.toml` (`middleware.src.services must not import GUI`, `middleware.src.services must not import PySide`, `middleware.src.services features must be independent`).

## Accessibility & Known Gaps

- **Keyboard navigation:** Layer selection, modifier toggling, and parameter adjustments are keyboard accessible via Tab and Arrow keys.
- **Screen-reader notes & known gaps:** Real-time canvas editing provides live polite announcements for layer reordering and filter application. Full WebGL viewport accessibility cutover is scheduled in Wave 8 #915.
# Hybrid Image Editor (`hie`)

| Field | Value |
|---|---|
| **Capability ID** | `hie` |
| **Service Package** | `middleware/src/services/hie/` |
| **Frontend View** | `frontend/src/tabs/editor/` |
| **Contract Schema** | `contracts/schemas/capability/hie.json` |
| **Contract SHA-256** | `b300d650a20b3df3cd66fc020c024b136af52e3b6aab1e7b38f51e50963ce075` |

## Overview

The Hybrid Image Editor (HIE) capability provides multi-modal image and video sequence editing with intelligent AI and RL co-pilot assistance (E-02 / #915). It wraps the HIE document session and render-graph pipeline into clean asynchronous bridge methods (`hie.open_document`, `hie.execute_edit`, `hie.export_document`, `hie.list_capabilities`), with seamless fallback when external ML models or GPU accelerators are unavailable.

## Public Surface

- **Python Domain Service (`middleware/src/services/hie/`):**
  - Commands: `HieOpenDocumentCommand`, `HieEditCommand`, `HieExportDocumentCommand`, `HieListCapabilitiesCommand`
  - Results: `HieOpenDocumentResult`, `HieEditResult`, `HieExportDocumentResult`, `HieListCapabilitiesResult`
  - Protocol: `HieServiceProtocol`
  - Implementation: `HieService`
- **Sidecar Handlers (`middleware/src/sidecar/handlers/hie.py`):**
  - Handlers: `handle_open_document`, `handle_execute_edit`, `handle_export_document`, `handle_list_capabilities`
- **Frontend Client (`frontend/src/hostclient/client.ts`):**
  - Typed methods: `hieOpenDocument`, `hieExecuteEdit`, `hieExportDocument`, `hieListCapabilities`
- **C++ Native Entrypoints:** none directly; delegates through Python orchestrator and submodule services.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/hie.json`
- **Methods:**
  - `hie.open_document`: Open or initialize an image/video document session.
  - `hie.execute_edit`: Apply editing operations (brush assistant, tone agent, crop composition) to an active document session.
  - `hie.export_document`: Render and export a document session to destination media.
  - `hie.list_capabilities`: Query supported operations and available neural model adapters.
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** Tool selection, preview, open media, and export controls are in natural tab order with visible focus states.
- **Screen-reader notes & known gaps:** Export progress and proposal generation alert through modal notifications and aria-live status containers. Multi-track audio and high-framerate timeline playback remain in PySide6 while shell migration finishes.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_hie_service.py -v
lint-imports
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
pytest middleware/test/services/test_hie_service.py middleware/test/sidecar/test_hie_dispatch.py -q
npm run test-frontend -- src/tabs/editor/HieEditorTab.test.tsx
```
