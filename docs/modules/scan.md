# Scan and Tag Service Module (`library.scan`)

| Field | Value |
|---|---|
| **Capability ID** | `library.scan` |
| **Service Package** | `middleware/src/services/scan/` |
| **Frontend View** | `frontend/src/views/library/ScanMetadataView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/scan.json` |
| **Contract SHA-256** | `fcd98e40ab0c2536dac82ba299e52e27a612a6bf7de94ed3e310ffb74ce7621d` |

## Overview

The Scan and Tag capability (`library.scan`, L-04 #898) scans filesystem directories for image assets (`png`, `jpg`, `jpeg`, `webp`, `gif`), extracts basic file properties (dimensions, file size), detects whether items already exist in the unified image database, and persists metadata and tags. Gate B compliant: operates in an offline/unattached mode when the vault is locked or database unavailable without opening unsealed stores or inventing database records.

## Public Surface

- **Python Service API (`middleware/src/services/scan/`):**
  - Commands: `ScanDirectoryCommand`, `SaveMetadataCommand`, `SuggestTagsCommand`
  - Results: `ScanDirectoryResult`, `SaveMetadataResult`, `SuggestTagsResult`
  - Coordinator: `ScanService` implementing `ScanServiceProtocol`
- **Sidecar Handlers (`middleware/src/sidecar/handlers/scan.py`):**
  - `handle_scan_directory`, `handle_save_metadata`, `handle_suggest_tags`
- **HostClient API (`frontend/src/hostclient/client.ts`):**
  - `scanDirectory(params: ScanDirectoryParams): Promise<ScanDirectoryResult>`
  - `scanSaveMetadata(params: SaveMetadataParams): Promise<SaveMetadataResult>`
  - `scanSuggestTags(params: SuggestTagsParams): Promise<SuggestTagsResult>`

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/scan.json` (`fcd98e40ab0c2536dac82ba299e52e27a612a6bf7de94ed3e310ffb74ce7621d`).
- **Methods (`contracts/methods.toml`):**
  - `scan.directory`: Scans directory with recursive and format filtering.
  - `scan.save_metadata`: Persists metadata assignments for scanned items.
  - `scan.suggest_tags`: Heuristic tag generation based on directory paths.

## Accessibility & Known Gaps

- **Keyboard parity:** Scan inputs, selection checkboxes, tag inputs, and batch action buttons are fully keyboard navigable.
- **Screen-reader notes & known gaps:** Live region announcements for discovered image counts and batch save results.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_scan_service.py -q
npm run --prefix frontend test -- src/views/library/ScanMetadataView.test.tsx
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
```
