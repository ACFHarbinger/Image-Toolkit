# ASP `no_valid_edges` triage — 2026-08-31

Evidence is the canonical full-97 log and merged reference
`anime_stitch_20260831_023504.json`. All 15 cases reached matching; none
reached the post-dedup edge filter with an edge left to validate.

| Case | Smart-selected | Raw matcher edges | Frames after spatial dedup | Filtered edges | Class |
|---|---:|---:|---:|---:|---|
| 25 | 9 | 20 | 2 | 0 | b |
| 34 | 16 | 33 | 2 | 0 | b |
| 43 | 23 | 55 | 5 | 0 | b |
| 46 | 22 | 57 | 2 | 0 | b |
| 48 | 21 | 50 | 3 | 0 | b |
| 50 | 15 | 39 | 2 | 0 | b |
| 52 | 15 | 39 | 3 | 0 | b |
| 55 | 18 | 30 | 2 | 0 | b |
| 66 | 18 | 38 | 2 | 0 | b |
| 70 | 32 | 65 | 2 | 0 | b |
| 76 | 8 | 18 | 2 | 0 | b |
| 79 | 27 | 75 | 2 | 0 | b |
| 90 | 34 | 50 | 2 | 0 | b |
| 93 | 10 | 6 | 2 | 0 | b |
| 95 | 37 | 102 | 3 | 0 | b |

`SPATIAL_DEDUP_PX=25` removes 7–34 of the smart-selected frames before
filtering. The raw matcher is therefore not the failure; its bridge edges are
discarded with their endpoints. A threshold-only relaxation is not a safe (a)
fix: `_reject_static_edges` then applies its independent 50 px floor, so it
would either still produce zero edges or weaken the duplicate-frame safety
invariant.

All 15 are **(b) candidates**: when dedup leaves an edgeless graph, propose
edges again between the retained adjacent frames, then run the existing filter
and fall back to SCANS if none survives. This is bounded to the failure path
and retains the current thresholds. It still needs a small instrumented probe
before being called recoverable; some sequences may be genuinely static or
unregisterable.

Persisted `edge_stage_counts` telemetry now records matcher output,
spatial-dedup frame/edge counts, filter input/output, HITL removals, and final
edges in session observability. Focused session tests: 13 passed.
