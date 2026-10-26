# Content Recommendation Engine (CRE) Service Module (`services/cre`)

| Field | Value |
|---|---|
| **Capability ID** | `cre` |
| **Service Package** | `middleware/src/services/cre/service.py` |
| **Frontend View** | N/A (Core Recommendation Service) |
| **Contract Schema** | `contracts/CONTRACTS.sha256` |
| **Contract SHA-256** | `fa9e3693e2291ced0dfb8ea17a7f05e5e7d4db54a64c8886140409356df48860` |

## Overview

The Content Recommendation Engine (CRE) provides multi-modal media item recommendation, hybrid semantic retrieval, cross-encoder reranking, and natural language explanation generation. Absorbed in W0-03 (#867 Phase C) and wrapping `submodules/CRE/src/` (`RecommendationPipeline`, `SQLiteStore`, and embedding pipelines), it provides ranking and discovery across media catalogs.

## Public Surface

- **Python Service API (`middleware/src/services/cre/`):**
  - Commands: `RecommendCommand`, `IndexMediaItemCommand`, `RecommendationItem`
  - Results: `RecommendResult`, `IndexMediaItemResult`
  - Handlers & Service: `CreService`, `CreServiceProtocol`
- **Core Pipeline:** `RecommendationPipeline` (`src.search.pipeline`), `SQLiteStore` (`src.data.store`), `Settings` (`src.core.config`).

## Contract & Routing

- **Contract Manifest:** `contracts/CONTRACTS.sha256` (`fa9e3693e2291ced0dfb8ea17a7f05e5e7d4db54a64c8886140409356df48860`).
- **Boundary Enforcement:**
  - `import-linter` contracts in `pyproject.toml` (`middleware.src.services must not import GUI`, `middleware.src.services must not import PySide`, `middleware.src.services features must be independent`).

## Accessibility & Known Gaps

- **Keyboard parity:** Query input, filter pills, and recommendation list navigation operate via Tab and Arrow keys.
- **Screen-reader notes & known gaps:** Scored results announce item title, media category, and relevance score with polite status regions.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_cre_service.py -v
lint-imports
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
```
