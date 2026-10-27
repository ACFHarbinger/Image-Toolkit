# Cel-Shaded Generator (CSG) Service Module (`services/csg`)

| Field | Value |
|---|---|
| **Capability ID** | `manga.colorization` / `manga.animation` / `manga.puppeteering` |
| **Service Package** | `middleware/src/services/csg/service.py` |
| **Frontend View** | `submodules/CSG/gui/src/tabs/` (migrating to Wave 8 #916 E-03 `frontend/src/views/manga/`) |
| **Contract Schema** | `contracts/CONTRACTS.sha256` |
| **Contract SHA-256** | `a4f0fd0f3b4e540630dddc3eaec3ec0e11e1e32419cff02dda892fb79373d8d4` |
| **Frontend View** | `frontend/src/views/manga/` (Wave 8 #916 E-03: `MangaWorkspaceView` + per-mode wrappers) |
| **Contract Schema** | `contracts/schemas/capability/csg.json` |
| **Contract SHA-256** | `b57fa3df7c9fdac12abbe617be1910b1c921283a962495768ba208ce0257e617` |

## Overview

The Cel-Shaded Generator (CSG) provides automated and interactive manga/lineart colorization (scribble guidance, reference-based optimal transport color transfer, screentone handling), 2D mesh generation with As-Rigid-As-Possible (ARAP) character puppeteering, and temporal animation color propagation. Backed by C++ high-performance processing in `backend/` and Python logic in `middleware/src/csg/`, it enables rich 2D illustration workflows. Absorbed in W0-03 (#867 Phase C) and unblocking Wave 8 editor #916 (E-03).

## Public Surface

- **Python Service API (`middleware/src/services/csg/`):**
  - Commands: `ColorizeScribbleCommand`, `ColorizeReferenceCommand`, `ArapDeformCommand`, `TemporalPropagateCommand`
  - Results: `ColorizeScribbleResult`, `ColorizeReferenceResult`, `ArapDeformResult`, `TemporalPropagateResult`
  - Handlers & Service: `CsgService`, `CsgServiceProtocol`
- **Core Primitives:** `colorize_scribble`, `colorize_reference`, `generate_mesh`, `arap_deform`, `colorize_scribble_sequence` (`middleware/src/csg/`). Upstream notes and the Comic Scene Graph licence: [`docs/csg/`](../csg/).
- **Bridge (`csg` capability, #916):** methods `csg.colorize_scribble`, `csg.colorize_reference`, `csg.arap_deform`, `csg.propagate_sequence` (schema `contracts/schemas/capability/csg.json`; handler `middleware/src/sidecar/handlers/csg.py`). Frontend calls them through `HostClient.csgColorizeScribble/…Reference/…ArapDeform/…PropagateSequence`.

## Contract & Routing

- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`a4f0fd0f3b4e540630dddc3eaec3ec0e11e1e32419cff02dda892fb79373d8d4`).
- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`b57fa3df7c9fdac12abbe617be1910b1c921283a962495768ba208ce0257e617`).
- **Feature Ledger Routing:** Tracks feature rows `manga.colorization`, `manga.animation`, and `manga.puppeteering` (Issue #916, wave-8) with routes `manga.colorization`, `manga.animation`, `manga.puppeteering`.
- **Boundary Enforcement:**
  - `import-linter` contracts in `pyproject.toml` (`middleware.src.services must not import GUI`, `middleware.src.services must not import PySide`, `middleware.src.services features must be independent`).

## Accessibility & Known Gaps

- **Keyboard navigation:** Palette selection, scribble intensity sliders, and deformation control points support full keyboard adjustment.
- **Screen-reader notes & known gaps:** Live color propagation status updates announce frame progress. Full Tauri canvas interactive tooling tracked in #916 E-03.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_csg_service.py -v
pytest middleware/test/sidecar/test_csg_dispatch.py -q
lint-imports
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
```
