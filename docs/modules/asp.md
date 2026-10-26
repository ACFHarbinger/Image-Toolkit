# Anime Stitch Pipeline (ASP) Service Module (`services/asp`)

| Field | Value |
|---|---|
| **Capability ID** | `stitch` |
| **Service Package** | `middleware/src/services/asp/service.py` |
| **Frontend View** | `gui/src/modules/stitch_workspace.py` (migrating to Wave 8 #914 E-01 `frontend/src/views/stitch/`) |
| **Contract Schema** | `contracts/CONTRACTS.sha256` |
| **Contract SHA-256** | `25bb1ff48ee734cd0ab7e3b3a0936c4ad12ee96988058c651d235a1188a48fd3` |
| **Contract SHA-256** | `6a45b8f32749068100d96710e9ad83f596745d32b6cb9702fc61e1997c228ea4` |

## Overview

The Anime Stitch Pipeline (ASP) provides high-performance multi-frame panorama and continuous anime sequence stitching. Backed by C++ pybind11 matching/bundle-adjustment engines in `backend/` and Python orchestration in `submodules/ASP/backend/src/` (`AnimeStitchPipeline`), it executes feature matching (LoFTR, ALIKED, ECC), photometric gain compensation, seam carving, and multi-band Poisson/Laplacian compositing. Absorbed in W0-03 (#867 Phase C) and unblocking Wave 8 editor #914 (E-01).

## Public Surface

- **Python Service API (`middleware/src/services/asp/`):**
  - Commands: `StitchCommand`, `MatchFramesCommand`, `RenderCanvasCommand`
  - Results: `StitchResult`, `MatchFramesResult`, `RenderCanvasResult`
  - Handlers & Service: `StitchService`, `StitchServiceProtocol`
- **Native & Core Delegate:** `AnimeStitchPipeline` in `asp_backend.core.pipeline.manager`, C++ bundle adjusters and solvers in `backend`.

## Contract & Routing

- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`25bb1ff48ee734cd0ab7e3b3a0936c4ad12ee96988058c651d235a1188a48fd3`).
- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`6a45b8f32749068100d96710e9ad83f596745d32b6cb9702fc61e1997c228ea4`).
- **Feature Ledger Routing:** Tracks feature row `stitch` (Issue #914, wave-8) with routes `stitch.stitch`, `stitch.graph`, `stitch.adjust`, `stitch.canvas`, `stitch.statistics`, `stitch.sequence-builder`, `stitch.hybrid`, `stitch.animation-clusters`.
- **Boundary Enforcement:**
  - `import-linter` contracts in `pyproject.toml` (`middleware.src.services must not import GUI`, `middleware.src.services must not import PySide`, `middleware.src.services features must be independent`).

## Accessibility & Known Gaps

- **Keyboard navigation:** Stitch configuration, sequence reordering, and canvas panning/zooming adhere to Tab/Shift-Tab and directional arrow shortcuts.
- **Progress Announcements:** Long-running multi-stage stitches announce progress percentages via polite screen-reader aria-live regions.
- **Known gaps:** Wave 8 #914 E-01 will port the PySide canvas view to Tauri 2 WebGL/Canvas2D.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_asp_service.py -v
lint-imports
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
```
