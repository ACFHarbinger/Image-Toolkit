# HIE Optimization Pipeline — Chat

Date: 2026-08-12

Implementation slice for Track 04 / Track 02 integration:

- Added `OptimizationPipeline` to expose PSO and differential evolution to
  frontends through the existing cancellable `JobHandle` contract.
- Python reference jobs remain the default because they provide deterministic
  per-iteration progress.
- Native `base.hie` PSO/DE execution is explicit (`backend="native"`) and
  capability-gated; unavailable builds fail clearly rather than silently
  changing behavior.

Validation: middleware pytest suite passes with 29 tests.
