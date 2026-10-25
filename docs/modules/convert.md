# Convert Service Module (`services/convert`)

| Field | Value |
|---|---|
| **Capability ID** | `convert` |
| **Service Package** | `middleware/src/services/convert/api.py` |
| **Frontend View** | `frontend/src/tabs/core/ConvertTab.tsx` (migrating to `frontend/src/features/convert/`) |
| **Contract Schema** | `contracts/schemas/capability/system.json` |
| **Contract SHA-256** | `5ee6901e620e3af9d87e0eee57f0d95746330e819b471c895b4f48e17a0201a0` |

## Overview

Provides single-file and batch image format conversion (`png`, `jpg`, `webp`, `bmp`, `tiff`, `gif`, `ico`) backed by the C++ `backend` `ImageFormatConverter` (`backend/src/core/convert.cpp`) with atomic temporary-file output commits so failed conversions never clobber existing destination files. Serves as the reference implementation for the Wave 0e `W0-17` (#881) Command/Handler service pattern.

## Public Surface

- **Python Service API (`middleware/src/services/convert/api.py`):**
  - Commands: `ConvertSingleCommand`, `BatchConvertCommand`
  - Results: `ConvertSingleResult`, `BatchConvertResult`
  - Handlers & Service: `ConvertSingleHandler`, `BatchConvertHandler`, `ConvertService`, `ConvertServiceProtocol`
- **C++ Native Entrypoints (`import backend`):** `backend.convert_single_image` via `ImageFormatConverter`.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/system.json` (total spine hash `db2448a4bdeabe1e4ed117d1df96cf7502ed74c7c1b95d27c342ebd8754977e3` in `contracts/CONTRACTS.sha256`).
- **Boundary Enforcement:**
  - `import-linter` contracts in `pyproject.toml` (`middleware.src.services must not import GUI`, `middleware.src.services must not import PySide`, `middleware.src.services features must be independent`).
  - `eslint-plugin-boundaries` in `frontend/eslint.config.mjs`.

## Accessibility & Known Gaps

- **Keyboard parity:** Format selector, path inputs, and Convert trigger are keyboard-navigable via Tab/Enter.
- **Screen-reader notes & known gaps:** Batch progress updates announce completion status; per-file live polite region announcements are tracked for the `P-01` (#894) Tauri view cutover.

## Verification

```bash
source .venv/bin/activate
PYTHONPATH=. pytest middleware/test/services/test_service_pattern.py -q
PYTHONPATH=. lint-imports
python middleware/validation/check_docs_freshness.py
```
