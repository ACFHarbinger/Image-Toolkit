# Scope: asp_test94 `affine_invalid:ratio=3.12 > 3`

**Status:** Design/scope only, no code. `asp_test94` is the one failing
known-good whose failure mode (`affine_invalid:ratio`) none of today's
experiments (CleanCP, overlap proposal, min-gap deferral, MAGSAC) touch.

## What `ratio` measures

`asp_backend/core/validation.py::_validate_affines` sorts strips by their
primary scroll-axis position, computes Euclidean gaps between consecutive
sorted positions, then flags invalid when `max_gap / median_gap > 3.0`
(`ratio`). It fires on **uneven spacing**: one gap much larger than the
typical gap (clustering / a big jump between strips).

## asp_test94 diagnosis

- Fallback: `affine_invalid:ratio=3.12211 > 3` (marginal: just over the 3.0
  threshold).
- Telemetry: `ba_residual_rms=70.8` (< 80), `cycle_error_rms=210.1` (< 300),
  `raw_edges=33` (> 10) — **all under the frozen registration-risk rule's
  ceilings**, so the metric rule would not flag it high-risk.
- Per-pair edges: **7 of 12 adjacent pairs have no observed correspondence**
  (`(1,2) (3,4) (5,6) (7,8) (8,9) (10,11) (11,12)`), leaving a fragmented
  chain (only `(0,1) (2,3) (4,5) (6,7) (9,10)` adjacent edges survive).
  BA then solves over the surviving skip edges, and the sequential+fill
  recovery (`_recover_affine_health` Retry 2) interpolates across the gaps —
  producing the uneven spacing that `ratio` flags.

**Conclusion: ratio=3.12 here is a downstream symptom of fragmented matching,
not a conservative threshold.** Unlike `min_gap` (44/58/61/96: clean metrics
BA 2–4 / cycle 5–11, frames genuinely close = high overlap = safe to
defer), asp_test94's metrics are *marginal* (BA 70.8 is 9 px from the 80
ceiling, cycle 210 is 90 px from 300) and the edge chain is genuinely
broken. `ratio` is doing real work here — relaxing/deferring it (the min-gap
treatment) could let a genuinely unreliable registration through as Raw ASP.

## Recommendation (scope)

1. **Do not defer/relax `ratio`** the way `min_gap` was. It is not proven
   conservative; this case is a genuine registration defect.
2. **The fix path is connectivity**, not a threshold change: asp_test94's
   missing adjacent edges are exactly what CleanCP (`ASP_CLEANCP_RESOLVE`)
   and the overlap proposal (`ASP_OVERLAP_PROPOSAL`) target. Verify whether
   either recovers the 7 missing edges; if the chain reconnects, the gaps
   even out and `ratio` normalizes on its own.
3. **Add diagnostic telemetry** so the two ratio origins are distinguishable
   in the fallback reason: record `max_gap`/`median_gap`/`min_gap` and the
   count of missing adjacent edges in the affine-health artifact. Then
   "ratio from matching fragmentation" vs "ratio from a genuine bimodal pan"
   (a legitimately two-speed sequence) are separable.
4. **Fold `ratio` into the existing affine_invalid reconciliation follow-up**
   (the team-open item already covering `min_gap`): calibrate `max_ratio`
   against the frozen corpus with the same frozen-then-evaluate discipline
   if it is to remain a hard pre-gate check, rather than assuming 3.0 is
   right or wrong.

## Files referenced

- `asp_backend/core/validation.py::_validate_affines` (ratio/min_gap checks)
- `asp_backend/core/pipeline/_affine_recovery.py::_recover_affine_health`
  (Retry 0 high-conf re-solve for `ratio=`; Retry 2 sequential+fill)
- `asp_backend/core/pipeline/run_stage.py` (adaptive thresholds, fallback)
- Frozen corpus `anime_stitch_latest_consolidated.json` (asp_test94)
