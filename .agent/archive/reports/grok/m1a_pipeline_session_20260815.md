# M1a — PipelineSession / shared stage protocol

**Date:** 2026-08-15  
**Issue:** ASP #26  
**Agent:** Grok

## Hypothesis

The three ASP runners cannot converge until they share a stage-orchestration
object. Extracting that object first, without rewriting either fork, is the
lowest-risk way to start M1.

## What changed

- New `backend/src/core/pipeline/session.py` in the ASP submodule.
- `AnimeStitchPipeline.run()` accepts optional `session=` / `pause_hook=`
  keyword arguments and always attaches `pipeline.last_session`.
- Bookkeeping calls sit next to existing log/return sites. Fallback
  functions, composite arguments, and control flow are unchanged.
- `_ProgressPipeline.run()` still fully overrides `run()`.

## What was not changed

- No pixel-producing function signature or default.
- No new HITL checkpoints in the canonical runner.
- No benchmark or GUI adapter work (M1b / M1c).
- No video `smart_select_frames` fix (ASP #27; isolated on purpose).

## Tests

`backend/test/core/test_pipeline_session.py` — session traces, digest
stability, pause-hook no-op vs record-only, HITL event-name parity with the
GUI, and `last_session` attachment on the existing N<2 `PipelineError`.

## Residual risk

Stage marks are point-in-time records at the original completion logs, not
a rewrite of `run()` into per-stage functions. M1b/M1c still have to move
real work onto this protocol.

## Status

Enabled bookkeeping. No algorithm default changed.
