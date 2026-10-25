# Library admin (`library_admin`)

| Field | Value |
|---|---|
| **Capability ID** | `library_admin` |
| **Service Package** | `middleware/src/services/library_admin/` |
| **Frontend View** | `frontend/src/views/library/LibraryManagement.tsx` |
| **Contract Schema** | `contracts/schemas/capability/library_admin.json` |
| **Contract SHA-256** | `87a6c1c4bbcd8620c700a853e4d981ff2d5063a5d5a08cc26fb125331358888d` |

## Overview

Management (#899) lists groups, subgroups, and tags and creates, removes, or merges them. The data browser (#900) pages one allowlisted table. A filter compares one column for equality. Nothing here opens `library.db`. With no store attached every result stays `available: false`.

## Public Surface

- **Python (`middleware/src/services/library_admin/admin.py`):** `catalog_result`, `mutate_result`, `browse_result`.
- **Sidecar:** `library_admin.catalog`, `library_admin.mutate`, `library_admin.browse`.
- **C++ Native Entrypoints:** none.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/library_admin.json`
- **Methods:** `library_admin.catalog`, `library_admin.mutate`, `library_admin.browse`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** the action select, name fields, Apply, table filters, Load, and page buttons are in the tab order.
- **Screen-reader notes & known gaps:** an unattached store is a status. A rejected name or unknown table is an alert. Cell editing, free-form WHERE clauses, and the ER diagram stay on the PySide6 browser. The ledger rows stay `pyside-only`.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_library_admin.py -q
```
