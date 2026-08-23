# Raw ASP quality: what actually separates wins from losses — 2026-08-23

Offline analysis only. No benchmark run. Inputs are the frozen 97-case corpus
`submodules/ASP/backend/benchmark/output/anime_stitch_latest_consolidated.json`
and Harbinger's completed 97/97 re-evaluation
`submodules/ASP/data/benchmarks/asp_evaluations_20260823.json` (explicit
`preference` field — never a derived coherence comparison; that proxy is what
produced the invalidated known-good set earlier today).

## 1. Raw ASP has essentially no genuine wins

Raw ASP shipped (`used_fallback=false`) on 32 of 97 cases. 30 of those carry a
preference:

| | count |
|---|---|
| preferred `simple` (SCANS) | 27 |
| preferred `asp` | 3 (`test40`, `test67`, `test73`) |

And `test40`'s own note reads *"ASP has many issues, but SCANS crop loss is
severe enough to overshadow them"* — the same least-bad pattern Harbinger
caught in the previous label set, so it is not an ASP quality win. Recurring
note text on the losses: *"SCANS is perfect"*, *"SCANS is near perfect"*,
*"ASP is a complete trash can of an output"*.

Only `asp_test67` is clean on every discriminating defect tag. It is the one
worked example of raw ASP producing a competitive output.

**Implication:** this is not a gating problem and not primarily a connectivity
problem. When ASP runs end to end, its render loses.

## 2. `color_shift` is ambient, not causal

Differential prevalence — rate of each ASP-attributed defect tag on the 12
`asp`-preferred cases vs the 61 `simple`-preferred cases. Raw frequency is
misleading here because these tags co-occur at 80-96% on the same cases.

| defect | loss % (n=61) | win % (n=12) | delta |
|---|---|---|---|
| blur | 41 | 17 | +24 |
| seam_line | 41 | 17 | +24 |
| banding | 39 | 17 | +23 |
| torn_anatomy | 46 | 25 | +21 |
| duplicated_strip | 20 | 0 | +20 |
| misordered_content | 33 | 17 | +16 |
| ghosting | 38 | 25 | +13 |
| crop_loss | 59 | 50 | +9 |
| geometry_warp | 2 | 0 | +2 |
| color_shift | 80 | **83** | **-3** |

`color_shift` is on 80% of losses and 83% of wins — it is wallpaper and
explains nothing about outcomes. `crop_loss` is highly prevalent but weakly
discriminating, consistent with Harbinger's "least-bad, not good" correction.

Two clusters actually discriminate:

- **seam/blending** — blur, seam_line, banding (+23 to +24)
- **content integrity** — torn_anatomy, duplicated_strip, misordered_content
  (+16 to +21). `duplicated_strip` is the cleanest single signal in the
  corpus: 20% of losses, 0% of wins.

**Caveat that limits all of the above: n=12 wins.** Every delta is fragile.
Treat the two-cluster split as the finding, not the individual percentages.

A second limit: the tags are binary. The notes say *"severe* color shift",
*"very intense* seam lines" — the schema cannot distinguish severe from trace,
which is plausibly why `color_shift` reads as ambient. Graded severity would
likely re-rank this table.

## 3. Fallback ratings answer a different question

`lab[name]['asp']` is a 1-5 score, not a path. The inspector loads
`{name}_anime_stitch.png` (`discovery.py:169`), i.e. the **shipped** output.
For the 65 fallback cases that is the Safe-ASP render, not raw ASP —
`raw_asp_path` is empty on those, so raw ASP output was never even saved.

Byte-comparing shipped vs simple: 52 fallbacks differ, **13 are byte-identical**
to `simple`. Those 13 are degenerate ratings (the same image rated against
itself). Anyone using the fallback slice to reason about raw ASP quality is
answering the wrong question — the clean slice is the 32 non-fallback cases.

## 4. Re-routing is half the corpus

| fallback reason | count |
|---|---|
| `disconnected_edge_graph` | 35 |
| `no_valid_edges` | 13 |
| `affine_invalid:*` (min_gap / ratio) | 15 |
| `seam_vis_gate` | 2 |
| `horizontal_scroll` | 1 |
| none (raw ASP shipped) | 32 |

48 of 97 never reach raw ASP because matching fails outright.

## 5. Photometric telemetry is dead across the whole corpus

`photometric.frames_corrected == 0`, `bg_lums == []`, `gain_range == null` on
**all 97 cases**.

The bench's own Step 4 (`bench_anime_stitch.py:1421-1449`) requires ≥3 frames
with a background mask carrying ≥1000 px before it computes any gain; the
empty `bg_lums` list means that block never populated. Production has a real
separate stage (`backend/src/core/pipeline/_photometric_stage.py`), so this is
**not** proof the production stage is inert — it is proof we have no
measurement of it. Given `color_shift` sits on ~80% of every case, that is a
blind spot over our most universal defect. Fix the telemetry before drawing any
conclusion about photometric behaviour.

## Reproduction

All figures come from reading the two JSON files above with `json.load` and
counting; no pipeline invocation, no benchmark. The defect field is
`defect_attribution['asp']`, falling back to the legacy flat `defects` list
when attribution is absent.
