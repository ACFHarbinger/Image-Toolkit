# #432 routing classifier — offline feasibility

**Claim:** `asp_evaluations_20260823.json` is a 2-way ASP-vs-SCANS human
scorecard, not a metrics→engine training set. A supervised multi-engine
router (ASP / SCANS / Hugin / Overmix) cannot be trained from it. A
binary ASP-vs-SCANS router is statistically weak (12 ASP-prefer cases)
and mostly rediscovers the existing fallback gates.

No training runs. Stats only. Joined 97/97 evals to
`submodules/ASP/backend/benchmark/output/anime_stitch_latest_consolidated.json`
(read-only).

## What the label file actually contains

97 reviewed cases. Fields: `asp`/`simple` (0–4 coherence), `preference`
(`asp`/`simple`/`tie`), `confidence`, `defects`, `notes`, `bboxes`
(only `asp_test01` has any), `edges` (always empty).

| Field | Counts |
|---|---|
| `asp` rating | 0:2 · 1:21 · 2:41 · 3:21 · 4:12 |
| `simple` (SCANS) rating | 1:6 · 2:19 · 3:35 · 4:37 |
| `preference` | simple **61** · tie 20 · asp **12** · missing 4 |
| `confidence` | 3:76 · 2:12 · 1:5 · missing 4 (same four as missing preference: 58, 72, 85, 86) |

Numeric `asp` vs `simple`: ASP better 5, equal 37, SCANS better 55.
`preference` disagrees with that numeric ordering on **19/93** cases
(rater picked a winner on a score tie, or a tie on a score gap). Use
`preference` as the routing label, not `asp > simple`.

Defects are ASP-centric tags (color_shift 87, crop_loss 67, torn_anatomy
45, …), not per-engine winners.

**Missing for a router:** Hugin rating, Overmix rating, GT rating,
chosen engine, any pre-stitch metric.

## Class balance if you forced a label

Decisive binary (`preference` in {asp, simple}): **73 cases, 12 ASP
(16.4%)**. Majority baseline = always route SCANS → **83.6%**.
`confidence >= 3` shrinks ASP wins to **6/58**.

That is not a 4-class engine problem. Wallpaper-mode routing (#431) is
ASP vs **Hugin**; this file never rates Hugin. Automated `metrics_hugin`
exists on only 37/97 rows of the joined run; `metrics_overmix` on 0/97.
Using those automated scores as labels would violate Ground Rules
(human coherence is the success criterion, never a proxy metric alone).

## Features the pipeline already emits

From the joined run (`run_fields` in
`submodules/ASP/backend/benchmark/evaluation/plugin/sample_fields.py`
is the intended schema):

**Pre-stitch / mid-pipeline (could exist before a final engine bake):**
`frames.count`, `matching.raw_edges` / `filtered_edges`,
`alignment.dy_cv` / `dx_cv`, `affine_health.*`,
`frame_selection.original_count` / `final_count`.

**Post-stitch (leakage if used as router inputs):** `used_fallback`,
`fallback_reason` / gate name, `comparison.ssim`/`verdict`,
`metrics_asp` / `metrics_simple`, GT SSIM. These are outcomes of
already running ASP and/or SCANS.

Trivial associations (pre-stitch vs `preference`):

- `dy_cv` median: ASP-prefer 0.32, SCANS-prefer 0.15, tie 0.21 — overlap
  dominates; SCANS-prefer mean is inflated by one 24.2 outlier.
- `frames.count` medians 15.5 / 11 / 8 — not separable.
- `affine_health.max_rotation` is **0.0 on all 97** in this dump;
  `affine_health.valid` is **null on all 97**. The wallpaper router's
  rotation/baseline features are not in this join.
- `dx_cv` has 1e7-scale outliers; means are unusable.

**Fallback is the real story:** 79/97 cases `used_fallback=True`
(seam_vis_gate 34, affine_invalid 21, composite_gate_sb 14,
no_valid_edges 7, coverage_gate 2, horizontal_scroll 1). 48 of 61
SCANS preferences already fell back. A classifier that sees
`used_fallback` is reading the answer.

Metric `comparison.verdict` is `comparable` on 72/97 — SSIM does not
track the human 61–12 SCANS lean. On the 17 rows where both human
numeric order and metric verdict are decisive, they disagree once.

## Leakage / split risks

1. **Outcome features.** Fallback gate, pair-SSIM, seam_coherence are
   computed after ASP (and often after SCANS). Illegal as router
   inputs unless the product is “run both, then pick,” which is not
   routing.
2. **Same 97 forever.** Any k-fold on this file is the same sequences
   the gates were tuned against. No held-out anime.
3. **Label date vs run date.** Evals are 2026-08-23; the consolidated
   run is a merge of many later experiments (metadata
   `timestamp` 2026-09-18, `merged: true`). Features are not the
   pipeline that produced the rated PNGs. Join is for orientation
   only.
4. **#654 non-determinism.** Product-path output is not stable
   run-to-run. A model fit to one dump will not match the next.
5. **Wallpaper vs stitcher.** #432 lives on the wallpaper-mode
   roadmap (metrics → engine, later a bandit). Current
   `evaluate_routing_gate` (#431) already routes ASP vs Hugin from
   rotation / step-ratio / luma divergence on frames — and the
   wallpaper pipeline currently passes **identity affines** into it
   (`wallpaper_pipeline.py`), so even that heuristic is under-fed.

## Verdict

| Question | Answer |
|---|---|
| Train a 4-engine router from this JSON? | **No.** No Hugin/Overmix/GT human labels. |
| Train ASP vs SCANS? | **Not worth it.** 12 positive ASP-prefer cases; 83.6% majority baseline; most SCANS wins co-occur with ASP fallback. |
| Do pipeline metrics exist? | **Yes**, in benchmark dumps / FiftyOne `run_fields`, not in the eval JSON. Join is possible; leakage is the default if you grab `metrics_*`. |
| What would make it feasible later? | Human Hugin (and optionally Overmix) preference on the same 97; a frozen pre-stitch feature snapshot taken *before* engine bake, from the same run that produced the rated PNGs; a hold-out set that is not the gate-tuning corpus; Slice-1 crop fix landed, then re-measure as the wallpaper roadmap already requires. |

Do not start a training run. The existing fallback gates plus
`evaluate_routing_gate` are the routing system; a learned classifier
needs labels those files do not have.

— Grok, 2026-09-18
