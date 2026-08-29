# ASP full-97 default baseline — 2026-08-29  ⚠️ BENCH-ADAPTER REGRESSION (bisected — see end)

> **Bottom line (added after bisection):** the "~43 → 8 composites" collapse is **not** a pipeline regression. It bisects to `b20d02c` (M1b, 2026-08-15), which switched the default bench from a legacy inline stitcher to the product `AnimeStitchPipeline.run()`. `ASP_BENCH_LEGACY=1` at current HEAD composites the probe cases fine. The alignment primitives are healthy; the product runner orchestrates them worse than the legacy inline path did — and the GUI shares the product runner. Full analysis in the **BISECTION RESULT** section at the end. The "core registration pipeline" framing in the sections below is the pre-bisection read — kept for the record, corrected at the end.

**Run by:** Claude, on Harbinger's authorization ("run #1 while I'm away").
**Config:** pure default pipeline — **no** `ASP_PLATE_*`, **no** `ASP_PLATE_MULTIPHASE`, **no** `ASP_PHASE_COMPOSITE`. Resource envs only (`ASP_BENCH_THREAD_CAP=8`, `MALLOC_ARENA_MAX=2`, abort 72/80, `ASP_RESOURCE_FLUSH_CUDA=1`). Current HEAD incl. BiRefNet VRAM fix `e720ccd1`.
**Host:** RTX 4080 Laptop / 31 GB. **Wall time:** 87.5 min (5251 s). 0 CUDA-OOM, 0 guardrail aborts, no crashes.
**Data:** `~/Downloads/Data/Tests/asp-full97-baseline-2026-08-29/` — 97 case dirs, frames symlinked from `~/Downloads/Data/Dump` (untouched), `ground_truth` symlinked, comparators copied.
**Result JSON:** `submodules/ASP/backend/benchmark/output/anime_stitch_20260829_100756.json`. Full per-case log in the scratch dir.

---

## Headline

| | this run (2026-08-29) | roadmap ref (2026-07-28 / 08-07) |
|---|---|---|
| **True ASP composites** | **8 / 97** | **43 / 97** (2026-08-07 full-97, `anime_stitch_20260807_045552.json` — the last full run before M1b; the "51" in the roadmap is the 2026-07-09 starting baseline) |
| Guarded fallbacks | 89 | ~46 |
| — **at the alignment stage** | **65** | **~1** |
| — at the composite stage | 24 | ~45 |
| GT-SSIM: ASP vs simple | **0.664 vs 0.694** (ASP worse) | 0.68 vs 0.72 area |
| verdict_counts asp_better / comparable / simple_better | 8 / 61 / 28 | 21 / 54 / 22 |

**This is a catastrophic regression in the core registration / edge-graph pipeline.** Alignment-stage fallbacks went from ~1 to 65. Two thirds of the corpus now never reaches the compositor. This is **not** multi-phase related (no plate flags were set) and it explains the multi-phase sweep's low yield — piecewise-P1 can't help a case whose registration fails first.

## Fallback-reason breakdown (89 fallbacks)

| reason | count | stage |
|---|---|---|
| `disconnected_edge_graph` | **40** | alignment (pre-BA edge-graph connectivity) |
| `seam_vis_gate` | 21 | composite (bench gate) |
| `no_valid_edges` | 12 | alignment (matcher produced nothing usable) |
| `affine_invalid` (min_gap / ratio) | 10 | alignment (Stage 7b validation) |
| `composite_gate_sb` | 3 | composite (bench gate) |
| `ratio` / `min_gap` / `horizontal_scroll` | 1 each | alignment |

`disconnected_edge_graph` + `no_valid_edges` = **52 cases** where the pairwise matcher produces too few / too-low-confidence edges for `filter_edge_graph` to keep the graph connected. Historically this class was ~1.

The 8 that still pass: `asp_test03, 04, 05, 39, 40, 88, 91, 97`.

## Suspected regression window: 2026-08-16 → 2026-08-27

No local full-97 JSON exists between 2026-08-07 and now to diff per-case, so this is by commit inspection. Prime suspects (all ASP submodule, all touch the matcher / edge proposal / run_stage):

1. **`763a3fb` fix(matching): avoid per-pair cuda stalls** + **`0c47eba` fix(models): avoid cuda flush during matcher offload** (2026-08-20) — direct matcher changes; "avoid per-pair stalls" implies reusing/batching matcher state that could change match counts or confidences.
2. **Orphaned-lineage recovery batch (2026-08-26/27):** `cb5d46e` (recover `_overlap_proposal`, `_estimators`, `_multiband`), `65e7192` (recover registration telemetry + risk gate), `6458f55` (reconcile `run_stage.py`), `fcfcb65` (mask type conversions). `_overlap_proposal` / `_estimators` are core to edge proposal — a recovered older version could easily collapse edge counts corpus-wide.
3. **`294afba` fix(asp): stop test83-style match stalls** (2026-08-16) — earlier matcher touch.
4. **`465328c` Trigger CleanCP on adjacent edge gaps** + **`e18f005` affine gap/adjacency diagnostics** (2026-08-24).

Low-probability variables to rule out while bisecting: the BiRefNet fp16 change `e720ccd1` (masks feed the matcher's FG exclusion — but the pre-fix sweep stage-1 already showed `disconnected_edge_graph` on test26/56/62/83, so the bulk predates it); `ASP_BENCH_THREAD_CAP` / `MALLOC_ARENA_MAX` (sweep ran both 4 and 8, same pattern); the symlinked-frame scratch layout (sweep used real `cp -r` copies, same pattern).

## Recommended next step — bisection

Do **not** build on the current pipeline for any quality work until this is fixed. Bisect with a **cheap fixed probe set** — pick ~6 `disconnected_edge_graph` cases that historically composited (e.g. `test10, 12, 27, 51, 63, 82`) and run just those (`--tests`, ~6 min/rev) at:

- `HEAD` (confirm: expect ~0/6 connected)
- just before the 2026-08-26 orphaned-lineage batch (`e068b50`'s parent or `465328c`)
- just before the 2026-08-20 matcher batch (`294afba` / `f8f624c`)
- a 2026-08-07-era commit (expect ~6/6 connected — the known-good anchor)

`git bisect` on the ASP submodule with "how many of the 6 reach the compositor" as the good/bad signal will land the offending commit in ~3–4 bench runs. Each is bench-gated → Harbinger auth per run, or one authorization for the whole bisect.

## Note

This baseline also *is* the roadmap Ground-Rule reference for any future default-ON decision — but it's unusable as a quality reference in its current state. Re-run after the regression is fixed.

---

## BISECTION RESULT (2026-08-29, Claude)

`git bisect` on the ASP submodule, 6-step, probe = 3 cases (`asp_test10, 27, 51`, all `disconnected_edge_graph`/`no_valid_edges` at HEAD), signal = "reaches the compositor".

**First bad commit: `b20d02c` — "feat(M1b): canonical bench adapter + injectable Safe ASP policy (#28)" (2026-08-15).**

Bisect chain: `1b52059` (08-07) good → `1938d51` (08-15) good → `64d8829` good → **`b20d02c` bad** → `8f5514c` bad → `37d6f49` bad → `d940c05` (HEAD) bad. `978afde`/`64d8829` (immediately before M1b) composite all 3 probe cases cleanly; `b20d02c` breaks all 3.

### It is a benchmark-adapter regression, NOT a pipeline regression

M1b's commit message: *"Default `process_dataset` now runs product `AnimeStitchPipeline.run()` then `SafeAspPolicy` … `ASP_BENCH_LEGACY=1` keeps the old fork."*

**Confirmed by running HEAD with `ASP_BENCH_LEGACY=1`:** `test10/27/51` all register (`Affine health: valid=True`) and reach the compositor — on **current HEAD**, with the same smart-selected frames. Only the default (M1b canonical) path fails them.

So:
- The alignment / matcher / bundle-adjust / edge-graph **primitives are fine at HEAD** — `ASP_BENCH_LEGACY=1` proves it.
- Before M1b, `process_dataset` stitched via a hand-tuned **inline sequence** in `bench_anime_stitch.py` (the code still there behind `ASP_BENCH_LEGACY=1`). M1b switched the default to `run_canonical_asp` → `AnimeStitchPipeline.run()` with product defaults.
- Both paths receive the **same** `_smart_select_frames(..., min_step_px=50.0)` output (line 1330, before the branch). The divergence is entirely in the stitch/registration orchestration.
- **The GUI stitch tab also uses `AnimeStitchPipeline`** (`gui/src/tabs/stitch_tab_backend.py`), so the product runner's behaviour here is user-facing — this isn't purely a measurement artifact.

### What this means for the numbers

- The roadmap's full-corpus history through 2026-08-15 (43 composites / 22 asp_better on 2026-08-07) measured the **legacy inline path**. Post-M1b bench numbers measure `AnimeStitchPipeline.run()`. **They are not comparable**, and the "43 → 8" drop is the measurement switch, not 3 weeks of pipeline rot.
- Whether `AnimeStitchPipeline.run()` itself *also* regressed since 08-07 is a separate open question (would need the product runner called directly at an old commit).

### Recommended fix direction

Diff `AnimeStitchPipeline.run()`'s registration → edge-filter → BA orchestration against the `ASP_BENCH_LEGACY=1` inline sequence in `bench_anime_stitch.py` (both are in-tree, side by side). Likely candidates: a matching-confidence / min-matches threshold, `filter_edge_graph` gate params, `ASP_TEMPORAL_RANGE`, or canvas/normalisation config that the legacy fork set explicitly and the product `run()` leaves at a stricter default. Fixing the product runner (not the bench) is the goal, since the GUI shares it.

**Interim:** the frozen-label / multi-phase discriminating-set analysis should treat `ASP_BENCH_LEGACY=1` as the reference until the product runner is fixed — or the multi-phase sweep should be re-run under `ASP_BENCH_LEGACY=1`… except the multi-phase renderer lives in `_composite_foreground`, which the legacy inline path also calls, so that's viable.
