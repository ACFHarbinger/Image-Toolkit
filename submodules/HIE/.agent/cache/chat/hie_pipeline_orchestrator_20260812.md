# HIE Pipeline Orchestrator — Chat

Date: 2026-08-12

Implementation slice for Track 04 (middleware + UI):

- Added `ProposalPipeline` in `middleware/src/hie_middleware/pipeline/`.
- Model adapters and RL policies now share registration, capability discovery,
  and serialized proposal envelopes for the PySide6 and Tauri frontends.
- The pipeline intentionally does not mutate documents; explicit acceptance and
  history integration remain the next safety boundary.
- Optional model failures remain localized to the adapter and are surfaced as
  `ModelUnavailable`.

Validation: middleware pytest suite passes with 26 tests.
