# Content Recommendation Engine (CRE) Service Module (`services/cre`)

| Field | Value |
|---|---|
| **Capability ID** | `cre` |
| **Service Package** | `middleware/src/services/cre/service.py` |
| **Frontend View** | N/A (Core Recommendation Service) |
| **Contract Schema** | `contracts/CONTRACTS.sha256` |
| **Contract SHA-256** | `8f3b63259aeee332f0b0ef1780647fdc1e5692c6d3e1a1d6b8b0aeb24360f303` |
| **Contract SHA-256** | `6a45b8f32749068100d96710e9ad83f596745d32b6cb9702fc61e1997c228ea4` |

## Overview

The Content Recommendation Engine (CRE) provides multi-modal media item recommendation, hybrid semantic retrieval, cross-encoder reranking, and natural language explanation generation. Absorbed in W0-03 (#867 Phase C) and relocated from `submodules/CRE/` to `middleware/src/cre/` in #1035 (phase E), it provides ranking and discovery across media catalogs. Reference docs (architecture, roadmaps, research notes) live in [`docs/cre/`](../cre/README.md).

## Public Surface

- **Python Service API (`middleware/src/services/cre/`):**
  - Commands: `RecommendCommand`, `IndexMediaItemCommand`, `RecommendationItem`
  - Results: `RecommendResult`, `IndexMediaItemResult`
  - Handlers & Service: `CreService`, `CreServiceProtocol`
- **Core Pipeline:** `RecommendationPipeline` (`middleware.src.cre.search.pipeline`), `SQLiteStore` / `EncryptedSQLiteStore` (`middleware.src.cre.data.store`), `Embedder` (`middleware.src.cre.data.embedder`), `Settings` (`middleware.src.cre.core.config`).

## Contract & Routing

- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`8f3b63259aeee332f0b0ef1780647fdc1e5692c6d3e1a1d6b8b0aeb24360f303`).
- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`6a45b8f32749068100d96710e9ad83f596745d32b6cb9702fc61e1997c228ea4`).
- **Boundary Enforcement:**
  - `import-linter` contracts in `pyproject.toml` (`middleware.src.services must not import GUI`, `middleware.src.services must not import PySide`, `middleware.src.services features must be independent`).

## Accessibility & Known Gaps

- **Keyboard parity:** Query input, filter pills, and recommendation list navigation operate via Tab and Arrow keys.
- **Screen-reader notes & known gaps:** Scored results announce item title, media category, and relevance score with polite status regions.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_cre_service.py -v
pytest middleware/test/cre -q
lint-imports
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
```
