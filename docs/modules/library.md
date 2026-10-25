# Library listings and image search (`library`)

| Field | Value |
|---|---|
| **Capability ID** | `library` |
| **Service Package** | `middleware/src/services/library/listings.py` |
| **Frontend View** | `frontend/src/views/library/Listings.tsx` |
| **Contract Schema** | `contracts/schemas/capability/library.json` |
| **Contract SHA-256** | `6deca491f5fefa9b57f32170f98dbe84dcfa19d33ee05548f97d6689cae3dac6` |

## Overview

Library listings and image search over the unified store (L-02 #896, L-03
#897). The capability mirrors the Rust `db.rs` surfaces
(`search_files`/`get_all_tags`/`get_all_groups`) that L-07 (#901) retires
once the Library pages route through `HostClient`. The module does not
open `library.db`: the sealed store reader arrives with the daemon lease
(Gate B stays closed); until then every result carries
`available: false` and the views show their unavailable notice.

## Public Surface

- **Python Service API (`middleware/src/services/library/listings.py`):**
  - `list_images_result(store, params)` filters through the store's
    `search_files` surface (single values for legacy parity, multi-select
    lists OR together) and normalizes rows to the contract record.
  - `list_tags_result(store)` / `list_groups_result(store)` project the
    tag list and the group → subgroups tree.
  - `LibraryStore` is the protocol the attached reader provides.
- **Bridge:** `library.list_images`, `library.list_tags`, `library.list_groups`.
- **C++ Native Entrypoints (`import backend`):** none. `library.db` is not opened here.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/library.json`
- **Methods (`contracts/methods.toml`):** `library.list_images`, `library.list_tags`, `library.list_groups`
- **Events (EventHub):** none

## Accessibility & Known Gaps

- **Keyboard parity:** groups and tags are checkboxes with labels; the
  filename filter is a labeled text input (Enter searches); pagination is
  two buttons with disabled states.
- **Screen-reader notes & known gaps:** aria-pressed on tag chips and
  subgroup buttons; the unavailable state is text. Thumbnails and image
  previews are L-01's surface (#895) and are not wired yet.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_library_listings.py middleware/test/sidecar/test_library_dispatch.py middleware/test/sidecar/test_server.py middleware/test/bridge/test_handshake_schema.py -q
```
