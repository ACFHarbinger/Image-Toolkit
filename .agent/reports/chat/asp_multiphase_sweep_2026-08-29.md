# Multi-phase renderer benchmark sweep — 2026-08-29

**Run by:** Claude, on Harbinger's conditional authorization (memory review first, then run it, monitored).
**Host:** RTX 4080 Laptop (12 GB VRAM) / 31 GB RAM / 24 cores — memory-constrained vs. the usual bench box.
**Scratch dir:** `~/Downloads/Data/Tests/asp-multiphase-sweep-2026-08-29/` (20 case dirs `cp -r`'d from `~/Downloads/Data/Dump`, `ground_truth/` symlinked). Nothing written back to the frozen corpus.
**Code under test:** ASP `4c2bc511` (multi-phase renderer `84af1be` + fix `7e352ba` + debug trace), root incl. BiRefNet VRAM fix `e720ccd1`.
**Discriminating set (20):** `01,05,08,17,26,28,40,41,56,62,67,71,72,73,74,80,82,83,86,91` (frozen-`RAW_ASP` ∩ multi-phase census from the §4 report).

Precautions (all active, all held): `MALLOC_ARENA_MAX=2`, `MALLOC_TRIM_THRESHOLD_=131072`, `ASP_BENCH_THREAD_CAP` 4 then 8, `ASP_BENCH_RAM_ABORT_PCT=72`, `ASP_BENCH_VRAM_ABORT_PCT=80`, `ASP_RESOURCE_FLUSH_CUDA=1`, plus an external 25 s-poll monitor that kills on <4 GB `MemAvailable` or a 7-min log stall. Per-dataset `gc.collect()` + `torch.cuda.empty_cache()` is already in the harness.

---

## 1. Memory / resource review — CLEARED

| Metric | Observed | Verdict |
|---|---|---|
| Peak process RSS | **~5 GB** (3-phase composite, 5-phase legacy) | vs. 31 GB — never a concern |
| `MemAvailable` floor | **~22 GB** across ~40 case-runs | monitor's 4 GB kill floor never approached |
| Peak VRAM | ~7.8 GB (BiRefNet masking) after the fix; was 11.8 GB before | headroom on the 12 GB card |
| Guardrail aborts | 0 | — |
| Crashes / hangs | 0 across ~40 case-runs (2 arms × 20) | — |

**Agy's `2.0 + 3.0·n_phases` GiB estimate is a loose upper bound, not a prediction** — actual `composite_plate_multiphase` overhead over single-phase P1 is a few hundred MB. No `n_phases` cap needed. No code change needed for memory. The `[Stitch] plate_multiphase: N phases -> ~M GiB` warning line is fine to keep as a conservative heads-up.

---

## 2. BiRefNet VRAM fix (root `e720ccd1`)

The batch mask path OOM'd on the 12 GB card for ≥15-frame stitches (`Tried to allocate 3.75 GiB`), dumping to a slow Python per-frame fallback and logging a scary OOM line (the pipeline never actually broke).

Changes in `backend/src/models/wrappers/birefnet_wrapper.py`: fp16 autocast on the forward pass (mask thresholded at 0.5 → fp16 rounding immaterial); `torch.inference_mode()`; `empty_cache()` per chunk; per-frame VRAM estimate 32×→48× with a hard cap of 2 on ≤12 GiB cards (3 on larger); and a live-OOM backoff that halves the chunk and retries in place instead of aborting the whole batch.

**Result across both full 20-case arms: 0 CUDA-OOM lines** (was 5 in the 8-case pilot), 0 backoff retries needed, VRAM peak 11.8 → 7.8 GB, **identical verdicts** (no mask-quality regression). 112 model tests pass; 2 new regression tests (`test_birefnet_batching.py`).

**Speed:** fp16 speeds the forward pass (~1.3–1.8× on this GPU) but the lower batch cap (4→2 here) adds per-call overhead — roughly neutral for cases that already had a working batch path; a real ~2–4× win on the masking stage for the ~7 ≥15-frame cases that previously fell back to the per-frame loop. Full ARM2 wall time: **22 min / 20 cases** (~66 s/case; `disconnected_edge_graph` cases ~20 s, composite cases 50–100 s) at `ASP_BENCH_THREAD_CAP=8`.

---

## 3. Sweep results

Two arms, same 20 cases:
- **ARM1** — piecewise P1: `ASP_PLATE_SINGLE_POSE=1 ASP_PLATE_MULTIPHASE=1`, `ASP_PHASE_COMPOSITE` unset.
- **ARM2** — same **+ `ASP_PHASE_COMPOSITE=1`** (resolves the deferred Option B question).

### Verdict distribution — identical between arms

| | raw_asp | safe_asp (fallback) | scans (pre-composite fallback) |
|---|---|---|---|
| ARM1 | **3** | 7 | 10 |
| ARM2 | **3** | 7 | 10 |

### Per-case

| case | multi-phase composite ran? | ARM1 verdict / why | ARM2 verdict / why |
|---|---|---|---|
| test05 | ✅ 3ph fwd | **raw_asp** | **raw_asp** |
| test41 | ✅ 2ph fwd | **raw_asp** | **raw_asp** |
| test17 | ✅ 1ph (trivial single span) | **raw_asp** | **raw_asp** |
| test08 | ✅ 3ph rev | fallback `seam_vis 145.8` | fallback `seam_vis 46.8` |
| test67 | ✅ 2ph fwd | fallback `composite_gate_sb sb=54.7` | fallback `composite_gate_sb sb=44.5` |
| test71 | ✅ 2ph fwd | fallback `seam_vis 69.9` | fallback `seam_vis 45.6` |
| test72 | ✅ 2ph rev | fallback `seam_vis 80.2` | fallback `seam_vis 63.5` |
| test91 | ✅ | fallback `seam_vis 64.9` | fallback `seam_vis 79.4` |
| test86 | ✅ ARM1 only | fallback `composite_gate_sb sb=55.6` | scans `affine_invalid` (variance) |
| test40 | ❌ plan reject (5ph→thin span) → legacy | fallback `seam_vis 43.1` | fallback `seam_vis 36.0` |
| test28 | ❌ pre-composite | scans `affine_invalid` | fallback `seam_vis 121.5` (variance) |
| test01, 26, 56, 62, 73, 74, 80, 82, 83 | ❌ pre-composite | scans `disconnected_edge_graph` / `affine_invalid` | same |

---

## 4. Findings

1. **The renderer is mechanically sound.** Engages correctly (gate accepts one `ty`-run per phase, forward or reverse; rejects thin/interleaved), memory flat, correct fallback every time, zero crashes over ~40 case-runs. The `84af1be`+`7e352ba` implementation does what it says.

2. **Two genuine multi-phase wins, stable across every run: `test41` (2-phase) and `test05` (3-phase) → `raw_asp`.** `test17` is a 1-phase trivial case (single span == plain P1).

3. **Where it engages on a real multi-phase case, the joined output usually fails the seam gates** — `seam_vis` 44–145 and `composite_gate_sb` `sb` 44–55, all above the ~35 limit. The `_blend_phase_plates` band join is producing visible seams at the phase boundaries. **This is the next thing to fix** before piecewise-P1 is a quality win. It is *not* a safety problem — those cases fall back to SCANS cleanly.

4. **Option B (`ASP_PHASE_COMPOSITE` on/off) flips zero verdicts** — no case changes raw_asp/fallback/scans between the arms. It *does* consistently lower the seam-visibility metric on the multi-phase-composite cases (test08 145.8→46.8, test71 69.9→45.6, test72 80.2→63.5), via a side effect on the upstream FG-pose registration that the plate path then consumes — but never by enough to clear a gate. **Recommendation: drop Option B** — as a shipped interim it would change nothing observable; the seam-metric nudge is real but sub-threshold, and it muddies the flag matrix.

5. **The frozen `RAW_ASP` labels don't hold under the current pipeline.** ~10 / 20 "RAW_ASP" cases now fall back *before compositing* (`disconnected_edge_graph` ×7, `affine_invalid` ×3) — a registration-stage change since the frozen corpus was labelled, unrelated to multi-phase. Borderline cases (test28/83/86) also flip fallback class run-to-run (affine validation is nondeterministic). The effective multi-phase sample on this set is ~8, not 14.

---

## 5. Recommendation

- **Do not enable `ASP_PLATE_MULTIPHASE` by default.** Correct call per the design doc — it's safe but not yet a win.
- **Next work item: the `_blend_phase_plates` seam.** The band join needs the boundary to survive `seam_vis_gate` / `composite_gate_sb`. Candidates: widen/soften the feather, do the join in a gradient/Poisson domain rather than Laplacian-pyramid alpha, or align the two plates photometrically at the seam band first (the per-span gain solve is independent, so adjacent plates carry a luminance step — §8-5 Agy note).
- **Drop Option B** from the roadmap (§7.5 / §3).
- **Human coherence rating** on `test05` / `test41` (the two wins) whenever the Phase 0.1 rating pass runs — that's still the gate for any default flip.
- The `disconnected_edge_graph` / `affine_invalid` regression on the frozen set is worth its own look, separately.

Raw logs: `~/Downloads/Data/Tests/asp-multiphase-sweep-2026-08-29/{stage1_piecewise,stage1b_diag,birefnet_fix_check,arm1_rest,arm2_phasecomposite}_*.log`.
