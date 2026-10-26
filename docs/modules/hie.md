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
pytest middleware/test/services/test_hie_service.py middleware/test/sidecar/test_hie_dispatch.py -q
npm run test-frontend -- src/tabs/editor/HieEditorTab.test.tsx
```
