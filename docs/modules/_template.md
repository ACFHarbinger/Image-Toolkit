# Module README Template

> Copy this file to `docs/modules/<feature>.md` when adding or migrating a capability. Keep the `Contract Schema` and `Contract SHA-256` entries synchronized with `contracts/CONTRACTS.sha256` — `python middleware/validation/check_docs_freshness.py` enforces this in CI.

| Field | Value |
|---|---|
| **Capability ID** | `<catalog-id>` (matches `migration/features.toml`) |
| **Service Package** | `middleware/src/services/<feature>/` (`api.py`) |
| **Frontend View** | `frontend/src/features/<feature>/` |
| **Contract Schema** | `contracts/CONTRACTS.sha256` |
| **Contract SHA-256** | `184e19fe7526c6a9f25ef4689e2df0cc7a2b4ad9cf77a0fbf5460be658376f83` |

## Overview

Briefly state what user-facing capability this module provides and which C++ `backend` or Python `middleware` subsystems it orchestrates.

## Public Surface

- **Python Service API (`middleware/src/services/<feature>/api.py`):**
  - Commands (`@dataclass(frozen=True)`): `...`
  - Results (`@dataclass(frozen=True)`): `...`
  - Protocols (`@runtime_checkable`): `...`
- **C++ Native Entrypoints (`import backend`):** `...`

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/<feature>.json`
- **Methods (`contracts/methods.toml`):** `...`
- **Events (EventHub):** `...`

## Accessibility & Known Gaps

- **Keyboard parity:** Document Tab order, Enter/Escape actions, and shortcut bindings from `keybindings.json`.
- **Screen-reader notes & known gaps:** List ARIA roles and any known screen-reader limitations.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_<feature>.py -q
python middleware/validation/check_docs_freshness.py
```
