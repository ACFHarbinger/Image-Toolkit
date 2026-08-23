# ASP connectivity vendor scope — 2026-08-23

Status: design/scoping only. No matching behavior changed.

## Problem and boundary

Stage 5–6 enumerates temporal pairs at separations 1, 2, and 3 in
`alignment/matching/_pairwise.py::_pairwise_match`, filters them, then falls
back on `no_valid_edges` or `disconnected_edge_graph` in `run_stage.py`.
This track targets pair proposal and graph connectivity only—not blending,
crop selection, or M2 selection policy. M2 calibration is paused pending
corrected labels, so evaluation begins with edge/connectivity telemetry.

## Vendor techniques and fit

### OpenCV: `BestOf2NearestRangeMatcher`

OpenCV builds only `(i, j)` pairs where `j < i + 1 + range_width`; it is a
candidate-pair constraint, not a different feature matcher. ASP already does
this manually with its fixed `{1,2,3}` span. Adapt it by extracting a named,
validated pair-proposal policy:

- retain every adjacent pair as the connectivity backbone;
- make skip range an opt-in policy with `3` as exact baseline equivalence;
- record candidate span/reason and pre/post-filter components in telemetry;
- reject a proposal before expensive matching if its candidate graph itself is
  disconnected.

It is not expected to recover missing edges by itself. Its falsifiable value
is less outlier/time exposure while retaining the baseline number of connected
registration graphs.

### Hugin: `CalculateImageOverlap` + `ImageGraph`

Hugin samples known camera transforms to estimate overlap, then builds graph
components. ASP has no poses before matching, so it cannot copy this directly.
The corresponding experiment needs **pre-match provisional geometry**:

1. Downsample static-background frames and retain Stage-4 masks.
2. Estimate cheap adjacent translations with phase correlation; keep confidence
   and reject implausible shifts.
3. Accumulate only reliable shifts into provisional strip coordinates; unknown
   positions remain unknown rather than interpolated.
4. Compute masked-background rectangle overlap for anchored pairs and build
   components.
5. Add/prioritize high-overlap or component-bridge pairs, but keep unknown
   pairs eligible through the adjacent backbone.

This plugs in immediately before `_pairwise_match` in `run_stage.py`, with
pair construction extracted into a pure proposal module. `_match_pair`,
`_filter_edges`, and the current post-match connectivity gate stay unchanged
in the first slice.

## Delivery and rejection criteria

1. **P0 telemetry-only:** extract `propose_temporal_pairs(N, range_width)`;
   record candidate reason/span, adjacent survival, components before/after
   filtering, and match-budget cut-off. Prove default equivalence by test.
2. **P1 default-off range policy:** compare ranges 1/2/3/4 on a frozen
   connectivity slice. Success means more connected graphs or less matching
   time, with no candidate-removal-induced disconnected graph.
3. **P2 default-off overlap proposal:** use provisional anchors only to add or
   prioritize bridge pairs. Success means a pre-registered increase in
   connected filtered graphs, followed by human review of each new Raw output.

Stop if anchors are often unavailable, the proposal exceeds the match budget,
or filtered-graph disconnections increase. Do not use post-BA affines to
choose Stage-5 pairs, remove adjacent pairs using inferred geometry, or claim
visual improvement from connectivity counts alone.

## Relevant source locations

- ASP pair enumeration: `backend/src/alignment/matching/_pairwise.py:399`
- ASP Stage 5–6/fallback: `backend/src/core/pipeline/run_stage.py:290`
- ASP filtering: `backend/src/core/pipeline/_filter_edges_mixin.py:24`
- OpenCV range loop: `vendor/OpenCV/modules/stitching/src/matchers.cpp:489`
- Hugin overlap/graph: `vendor/Hugin/src/hugin_base/algorithms/basic/CalculateOverlap.cpp:33`,
  `vendor/Hugin/src/hugin_base/algorithms/optimizer/ImageGraph.cpp:70`
