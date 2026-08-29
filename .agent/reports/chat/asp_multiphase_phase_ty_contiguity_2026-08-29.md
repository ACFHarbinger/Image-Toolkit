# ASP multi-phase phase/`ty` contiguity measurement

**Date:** 2026-08-29  
**Scope:** 20 frozen-`RAW_ASP` cases intersected with Antigravity's 59-case multi-phase census: `01, 05, 08, 17, 26, 28, 40, 41, 56, 62, 67, 71, 72, 73, 74, 80, 82, 83, 86, 91`.

## Verdict

This is a mixed result. Fourteen of 20 cases (70.0%) have non-interleaving phase bands in canvas-`ty` order, while six (30.0%) interleave phase IDs and cannot be represented by a piecewise vertical band stack. Option A therefore requires a **hard runtime contiguity gate**, with expected eligibility of **14/20 (70.0%)** on this discriminating set. The six non-contiguous cases must fall through to legacy (or a later Option C/D path).

The design's literal `phase_ids`-is-monotonic-*non-decreasing* predicate passes only 10/20 (50.0%). The other five contiguous cases pan in the opposite direction, so their IDs are monotonic non-*increasing* after sorting by `ty`; their bands are well-defined but must be joined in physical canvas order rather than assuming selection-phase order. The runtime gate should thus accept either monotone direction (equivalently: every phase occupies one `ty` run), record the direction, and reject only actual interleaving.

Adjacent phase bands overlap substantially in every eligible case (740.0–1080.0 px; values below); this is expected because source frames are nearly a frame-height tall and provides a blend region, not evidence of interleaving. The reported overlap is the maximum of `max(0, min(end_a,end_b)-max(start_a,start_b))` over adjacent phase-span envelopes, where an envelope is `[min(ty), max(ty + frame_height)]`.

## Method

The frozen JSONs preserve useful affine telemetry but not, consistently, an index-aligned selected-path list after spatial dedup. To avoid pairing stale phase diagnostics with a different frame list, this measurement used the benchmark's smart-selected paths in selection order, called `detect_animation_phases(paths)` and `phase_spans()` from `ingestion/frame_selection/phases.py`, then made one serial **registration-only** pass per case: load/normalize frames, adjacent-pair template/phase-correlation matching (`ASP_TEMPORAL_RANGE=1`, no LoFTR), and translation bundle adjustment. It did not call the compositor, renderer, gates, or benchmark harness. The raw JSON is retained outside the repo at `~/Downloads/Data/Tests/asp_phase_ty_contiguity_20260829.json`.

`F→(ty,p)` below is the requested frame-index to `(ty, phase_id)` table, sorted by increasing `ty`; values are pixels and rounded to 0.1. “Forward” means non-decreasing phase IDs in this order; “reverse” means non-increasing but still one band per phase.

## Per-case results

| Case | Frames / phases | Selection-order `phase_spans` | `ty` bands | Direction | Max adjacent overlap | `ty`-sorted `F→(ty,p)` |
|---|---:|---|---|---|---:|---|
| `asp_test01` | 16 / 3 | `(0,0,10), (1,11,14), (2,15,15)` | interleaved | mixed | 1255.1 | `8→(-198.3,0); 7→(-139.8,0); 9→(-138.9,0); 0→(0.0,0); 6→(36.5,0); 10→(38.5,0); 1→(193.9,0); 5→(216.5,0); 11→(219.0,1); 2→(382.5,0); 4→(393.8,0); 12→(445.0,1); 3→(449.1,0); 13→(716.5,1); 14→(1033.4,1); 15→(1395.8,2)` |
| `asp_test05` | 17 / 3 | `(0,0,7), (1,8,14), (2,15,16)` | contiguous | reverse | 885.0 | `16→(-3143.2,2); 15→(-2947.2,2); 14→(-2751.2,1); 13→(-2556.2,1); 12→(-2361.2,1); 11→(-2166.2,1); 10→(-1971.2,1); 9→(-1776.2,1); 8→(-1581.2,1); 7→(-1386.2,0); 6→(-1191.2,0); 5→(-996.2,0); 4→(-801.2,0); 3→(-606.0,0); 2→(-390.5,0); 1→(-195.2,0); 0→(0.0,0)` |
| `asp_test08` | 9 / 3 | `(0,0,3), (1,4,6), (2,7,8)` | contiguous | forward | 885.0 | `0→(0.0,0); 1→(195.0,0); 2→(390.0,0); 3→(585.0,0); 4→(780.0,1); 5→(975.0,1); 6→(1170.0,1); 7→(1365.0,2); 8→(1560.0,2)` |
| `asp_test17` | 19 / 2 | `(0,0,4), (1,5,18)` | interleaved | mixed | 1274.0 | `3→(-349.2,0); 4→(-310.4,0); 2→(-310.4,0); 5→(-194.0,1); 1→(-194.0,0); 6→(-0.1,1); 0→(0.0,0); 7→(194.9,1); 8→(389.9,1); 9→(584.9,1); 10→(779.9,1); 11→(974.9,1); 12→(1169.9,1); 13→(1364.9,1); 14→(1559.9,1); 15→(1754.9,1); 16→(1949.9,1); 17→(2144.9,1); 18→(2339.9,1)` |
| `asp_test26` | 7 / 2 | `(0,0,1), (1,2,6)` | contiguous | forward | 740.0 | `0→(0.0,0); 1→(159.2,0); 2→(338.2,1); 3→(537.0,1); 4→(736.0,1); 5→(935.0,1); 6→(1134.0,1)` |
| `asp_test28` | 22 / 4 | `(0,0,15), (1,16,17), (2,18,19), (3,20,21)` | contiguous | forward | 884.3 | `0→(0.0,0); 1→(195.0,0); 2→(390.0,0); 3→(585.0,0); 4→(780.0,0); 5→(975.0,0); 6→(1170.0,0); 7→(1365.0,0); 8→(1560.0,0); 9→(1755.4,0); 10→(1983.7,0); 11→(2272.9,0); 12→(2639.0,0); 13→(2950.3,0); 14→(3207.0,0); 15→(3459.3,0); 16→(3655.0,1); 17→(3850.0,1); 18→(4045.8,2); 19→(4302.6,2); 20→(4682.0,3); 21→(5087.7,3)` |
| `asp_test40` | 18 / 5 | `(0,0,6), (1,7,7), (2,8,9), (3,10,14), (4,15,17)` | contiguous | forward | 885.0 | `0→(0.0,0); 1→(195.0,0); 2→(390.0,0); 3→(585.0,0); 4→(780.0,0); 5→(975.0,0); 6→(1170.0,0); 7→(1365.0,1); 8→(1560.0,2); 9→(1755.0,2); 10→(1950.0,3); 11→(2145.0,3); 12→(2340.0,3); 13→(2535.0,3); 14→(2730.0,3); 15→(2925.0,4); 16→(3120.0,4); 17→(3315.0,4)` |
| `asp_test41` | 10 / 2 | `(0,0,6), (1,7,9)` | contiguous | forward | 870.2 | `0→(0.0,0); 1→(195.0,0); 2→(389.0,0); 3→(580.0,0); 4→(771.5,0); 5→(963.5,0); 6→(1154.9,0); 7→(1345.7,1); 8→(1516.6,1); 9→(1774.6,1)` |
| `asp_test56` | 8 / 2 | `(0,0,0), (1,1,7)` | contiguous | reverse | 812.8 | `7→(-1438.0,1); 6→(-1243.0,1); 5→(-1048.0,1); 4→(-853.0,1); 3→(-658.0,1); 2→(-463.0,1); 1→(-267.2,1); 0→(0.0,0)` |
| `asp_test62` | 14 / 2 | `(0,0,10), (1,11,13)` | contiguous | forward | 885.0 | `0→(0.0,0); 1→(195.0,0); 2→(390.0,0); 3→(585.0,0); 4→(780.0,0); 5→(975.0,0); 6→(1170.0,0); 7→(1365.0,0); 8→(1560.0,0); 9→(1755.0,0); 10→(1950.0,0); 11→(2145.0,1); 12→(2340.0,1); 13→(2535.0,1)` |
| `asp_test67` | 15 / 2 | `(0,0,4), (1,5,14)` | interleaved | mixed | 1458.9 | `3→(-483.6,0); 4→(-480.4,0); 2→(-388.4,0); 5→(-378.9,1); 1→(-195.0,0); 6→(-179.2,1); 0→(0.0,0); 7→(15.9,1); 8→(210.9,1); 9→(405.9,1); 10→(600.9,1); 11→(795.9,1); 12→(990.9,1); 13→(1185.9,1); 14→(1380.9,1)` |
| `asp_test71` | 7 / 2 | `(0,0,1), (1,2,6)` | contiguous | forward | 885.0 | `0→(0.0,0); 1→(195.0,0); 2→(390.0,1); 3→(585.0,1); 4→(780.0,1); 5→(976.0,1); 6→(1245.0,1)` |
| `asp_test72` | 17 / 4 | `(0,0,5), (1,6,7), (2,8,9), (3,10,16)` | contiguous | reverse | 883.7 | `16→(-4511.8,3); 15→(-4149.2,3); 14→(-3786.6,3); 13→(-3378.3,3); 12→(-3046.7,3); 11→(-2744.5,3); 10→(-2471.9,3); 9→(-2173.8,2); 8→(-1845.6,2); 7→(-1465.8,1); 6→(-1177.7,1); 5→(-981.4,0); 4→(-785.1,0); 3→(-588.9,0); 2→(-392.6,0); 1→(-196.3,0); 0→(0.0,0)` |
| `asp_test73` | 19 / 2 | `(0,0,7), (1,8,18)` | interleaved | mixed | 1367.8 | `10→(-1816.4,1); 11→(-1752.9,1); 9→(-1752.0,1); 12→(-1561.7,1); 8→(-1559.9,1); 18→(-1367.2,1); 13→(-1366.7,1); 7→(-1364.9,0); 17→(-1173.9,1); 14→(-1173.6,1); 6→(-1170.0,0); 16→(-1077.2,1); 15→(-1077.1,1); 5→(-975.0,0); 4→(-780.0,0); 3→(-585.0,0); 2→(-390.0,0); 1→(-195.0,0); 0→(0.0,0)` |
| `asp_test74` | 23 / 2 | `(0,0,18), (1,19,22)` | interleaved | mixed | 1665.0 | `16→(-1265.5,0); 15→(-1265.5,0); 17→(-1168.6,0); 14→(-1168.6,0); 18→(-975.0,0); 13→(-974.9,0); 19→(-780.0,1); 12→(-780.0,0); 20→(-585.0,1); 11→(-585.0,0); 21→(-390.0,1); 10→(-390.0,0); 22→(-195.0,1); 9→(-195.0,0); 0→(0.0,0); 8→(0.0,0); 1→(195.0,0); 7→(195.0,0); 2→(389.0,0); 6→(389.0,0); 3→(505.4,0); 5→(505.4,0); 4→(544.2,0)` |
| `asp_test80` | 20 / 5 | `(0,0,15), (1,16,16), (2,17,17), (3,18,18), (4,19,19)` | contiguous | reverse | 885.0 | `19→(-3718.9,4); 18→(-3517.0,3); 17→(-3315.1,2); 16→(-3120.0,1); 15→(-2925.0,0); 14→(-2730.0,0); 13→(-2535.0,0); 12→(-2340.0,0); 11→(-2145.0,0); 10→(-1950.0,0); 9→(-1755.0,0); 8→(-1560.0,0); 7→(-1365.0,0); 6→(-1170.0,0); 5→(-975.0,0); 4→(-780.0,0); 3→(-585.0,0); 2→(-390.0,0); 1→(-195.0,0); 0→(0.0,0)` |
| `asp_test82` | 23 / 3 | `(0,0,2), (1,3,3), (2,4,22)` | interleaved | mixed | 1080.0 | `22→(-2384.6,2); 21→(-2189.6,2); 20→(-1994.6,2); 19→(-1798.5,2); 18→(-1594.0,2); 17→(-1381.2,2); 16→(-1174.3,2); 15→(-973.3,2); 14→(-778.2,2); 13→(-583.2,2); 12→(-388.2,2); 11→(-193.2,2); 0→(0.0,0); 10→(1.8,2); 1→(195.0,0); 9→(196.8,2); 2→(390.0,0); 8→(391.8,2); 3→(585.0,1); 7→(586.7,2); 4→(777.1,2); 6→(778.0,2); 5→(841.5,2)` |
| `asp_test83` | 18 / 3 | `(0,0,0), (1,1,1), (2,2,17)` | contiguous | forward | 885.0 | `0→(0.0,0); 1→(195.0,1); 2→(390.0,2); 3→(585.0,2); 4→(780.0,2); 5→(975.0,2); 6→(1170.0,2); 7→(1365.0,2); 8→(1560.2,2); 9→(1755.6,2); 10→(1984.7,2); 11→(2180.1,2); 12→(2375.1,2); 13→(2570.1,2); 14→(2765.1,2); 15→(2960.1,2); 16→(3155.1,2); 17→(3350.1,2)` |
| `asp_test86` | 29 / 2 | `(0,0,14), (1,15,28)` | contiguous | forward | 799.1 | `0→(0.0,0); 1→(194.9,0); 2→(384.0,0); 3→(572.7,0); 4→(867.8,0); 5→(1269.4,0); 6→(1743.9,0); 7→(2196.7,0); 8→(2628.0,0); 9→(3037.6,0); 10→(3425.6,0); 11→(3792.2,0); 12→(4137.3,0); 13→(4461.1,0); 14→(4763.4,0); 15→(5044.4,1); 16→(5303.8,1); 17→(5541.9,1); 18→(5758.6,1); 19→(5953.8,1); 20→(6148.8,1); 21→(6343.8,1); 22→(6538.8,1); 23→(6733.8,1); 24→(6928.8,1); 25→(7123.8,1); 26→(7318.8,1); 27→(7513.8,1); 28→(7708.8,1)` |
| `asp_test91` | 17 / 2 | `(0,0,3), (1,4,16)` | contiguous | forward | 1078.6 | `2→(-254.1,0); 1→(-190.8,0); 3→(-190.0,0); 0→(0.0,0); 4→(1.4,1); 5→(196.4,1); 6→(391.4,1); 7→(586.4,1); 8→(781.4,1); 9→(976.4,1); 10→(1171.4,1); 11→(1366.4,1); 12→(1561.4,1); 13→(1756.4,1); 14→(1951.4,1); 15→(2146.4,1); 16→(2341.4,1)` |

## Decision against §4

The corpus does not support an unconditional band-stack renderer. It does support Option A for a substantial majority, provided the contiguity gate is installed before per-phase plate construction. The gate must distinguish reverse pan direction from interleaving:

1. Sort final compositor-frame indices by `affines[i][1,2]`.
2. Collapse the sorted `phase_ids` into runs.
3. Permit exactly one run per phase (forward or reverse); choose band joins in sorted-canvas order.
4. Reject repeated phase runs as non-contiguous and retain the current legacy fallback.

That gate covers 70.0% of the multi-phase `RAW_ASP` discriminating set measured here. The remaining 30.0%—`01, 17, 67, 73, 74, 82`—must retain the legacy fallback until an Option C/D-capable path exists.
