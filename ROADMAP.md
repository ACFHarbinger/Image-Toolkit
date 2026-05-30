# AnimeStitchPipeline — Improvement Roadmap

*Based on: `reports/ASP_CV_Research_and_Improvement_Plan.md` (2026-05-26)*
*Roadmap created: 2026-05-30*
*Benchmark baseline: `anime_stitch_20260526_192625.json` — 22/22 (100%) success, avg sharpness 33.14*

---

## Environment Notes

| Package | Status |
|---|---|
| `kornia 0.8.2` | Installed — includes LoFTR, **LightGlue + ALIKED** (via `LightGlueMatcher('aliked')`) |
| `torch 2.9.1` | Installed |
| EfficientLoFTR | ✅ Installed via HuggingFace `zju-community/efficientloftr` (transformers 4.57.2) |
| SEA-RAFT | **No pip package** — install from `princeton-vl/SEA-RAFT` (GitHub) |
| Real-ESRGAN | `pip install realesrgan basicsr` |
| RoMa v2 | Install from `Parskatt/RoMaV2` (GitHub) |
| XFeat | Install from `verlab/accelerated_features` (GitHub) |
| JamMa | Install from `leoluxxx/JamMa` (GitHub) |

---

## Phase 1 — Quick Wins (≤ 1 day each, no new dependencies)

| # | Task | File(s) | Weakness | Status |
|---|---|---|---|---|
| **P1.1** | Wire `_cluster_animation_phases` into `_render_median` | `rendering.py` | W3 ghosting | ✅ **DONE** (already in code, lines 462–495) |
| **P1.2** | Variable-step `renderer='first'` for high-dy_cv (> 0.20) | `pipeline.py` Stage 10 | W2 test16 | ✅ **DONE** |
| **P1.3** | Confidence-weighted temporal median | `rendering.py` | W3 ghosting | ✅ **DONE** |
| **P1.4** | Replace LoFTR with EfficientLoFTR | `models/efficient_loftr_wrapper.py` + `pipeline.py` | W6 speed | ✅ **DONE** (HuggingFace transformers, auto-fallback to LoFTR) |
| **P1.5** | Structured grid sampling for non-LoFTR edges (4×4 grid, n=50) | `matching.py` | W7 BA quality | ✅ **DONE** |
| **P1.6** | Trajectory smoothness regularisation in BA (StabStitch, λ=0.1) | `bundle_adjust.py` | warp jitter | ✅ **DONE** |
| **P1.7** | Auto-activate MFSR when canvas Laplacian variance < 20 | `pipeline.py` Stage 10.5 | W1 blurry | ✅ **DONE** |
| **P1.8** | Auto-trigger diffusion inpainting when coverage < 95% | `pipeline.py` Stage 13 | W4 test7 gaps | ✅ **DONE** |
| **P1.9** | Bidirectional midplane projection (StabStitch++) | `pipeline.py` Stage 9 | distortion | ✅ **DONE** |

### Phase 1 Expected Gains

| Metric | Baseline | P1 Target |
|---|---|---|
| avg sharpness | 33.14 | 35–37 |
| avg ghosting | 22.17 | 14–16 |
| test16 (SCANS inversion) | SCANS=38.9 > ASP=32.4 | **Eliminated** |
| test7 coverage | 81.5% | 95%+ |

---

## Phase 2 — Core Quality Upgrades (3–7 days each, some new dependencies)

| # | Task | File(s) | Weakness | Status |
|---|---|---|---|---|
| **P2.1** | SEA-RAFT flow refinement replacing ECC (Stage 8) | New `anim/flow_refine.py` + `pipeline.py` | W5 flat regions | ⬜ TODO (needs GitHub install) |
| **P2.2** | Real-ESRGAN `anime_6B` post-processing | New `anim/super_res.py` + `pipeline.py` | W9 resolution | ⬜ TODO (pip install realesrgan) |
| **P2.3** | ALIKED + LightGlue sparse fallback tier (Attempt 1b) | New `models/aliked_lg_wrapper.py` + `matching.py` | W6 coverage | ✅ **DONE** (kornia 0.8.2 has both) |
| **P2.4** | SAM-based semantic seam routing | New `anim/seam_guide.py` + `compositing.py` | W8 char. seams | ⬜ TODO |
| **P2.5** | Soft-seam diffusion blending (DSFN technique) | `compositing.py` | seam artifacts | ⬜ TODO |
| **P2.6** | Per-segment photometric correction (SAM segments) | `pipeline.py` Stage 4.5 | colour bleed | ⬜ TODO |
| **P2.7** | RecDiffusion border rectangling | New `anim/rectangling.py` | W10 borders | ⬜ TODO (diffusion backbone needed) |
| **P2.8** | RoMa v2 dense-warp last-resort matcher | New `models/roma_wrapper.py` + `matching.py` | W7 hard pairs | ⬜ TODO (GitHub install) |
| **P2.9** | Segment-guided matching (AnimeInterp technique) | `matching.py` | low-texture tests | ⬜ TODO |

### Phase 2 Expected Gains (cumulative with P1)

| Metric | P1 Target | P2 Target |
|---|---|---|
| avg sharpness | 35–37 | 42–48 |
| avg ghosting | 14–16 | 10–12 |
| char. seam artifacts | ~4–6 tests | **0** |
| output resolution | 1× source | **2–4× source** |
| seam gradient | ~4.8 | 5.5–6.5 |

---

## Phase 3 — Research-Grade (1–2 weeks each, significant infrastructure)

| # | Task | Notes | Status |
|---|---|---|---|
| **P3.1** | EfficientLoFTR drop-in (GitHub install + wrapper update) | 2.5× faster vs LoFTR | ⬜ TODO |
| **P3.2** | JamMa for 4K batch processing (O(N) Mamba attention) | Linear scaling for 4K frames | ⬜ TODO |
| **P3.3** | ToonCrafter ghost fill for animation phases | Cyclic animation ghosting removal | ⬜ TODO |
| **P3.4** | SRStitcher unified diffusion fusion | Anime diffusion backbone replaces Laplacian | ⬜ TODO |
| **P3.5** | Fine-tune SEA-RAFT on LinkTo-Anime dataset | 30–50% more bg correspondences on anime | ⬜ TODO |
| **P3.6** | Fine-tune EfficientLoFTR on synthetic anime pairs | Reduce TM/PC fallback from ~15% to <5% | ⬜ TODO |

---

## Weaknesses Reference

| ID | Description | Priority | Phase |
|---|---|---|---|
| W1 | Low-sharpness cluster (tests 2, 3, 19, 20) — blurry/dark sources | High | P1.7 |
| W2 | test16 inversion — SCANS beats ASP (dy_cv=0.297) | High | P1.2 |
| W3 | High ghosting avg 22.17 — animation phases not fully filtered | High | P1.1 ✅, P1.3 |
| W4 | test7 coverage 81.5% — diagonal motion black corners | High | P1.8 |
| W5 | ECC fails on flat regions (~30% of pairs) | Medium | P2.1 |
| W6 | LoFTR 2021 vintage — O(N²) attention bottleneck on 4K | Medium | P1.4/P3.1 |
| W7 | Synthetic BA anchor points bias the LM solver | Medium | P1.5 ✅ |
| W8 | No semantic seam routing — seams can bisect characters | Medium | P2.4 |
| W9 | No super-resolution post-processing | Low | P2.2 |
| W10 | Hard 30px border crop — irregular edges remain | Low | P2.7 |

---

## Implementation Log

| Date | Item | Result |
|---|---|---|
| 2026-05-30 | P1.1 audit | Already implemented in `rendering.py:462–495` |
| 2026-05-30 | P1.2 | Implemented dy_cv > 0.20 → renderer='first' in `pipeline.py` |
| 2026-05-30 | P1.5 | Implemented `_sample_bg_points_grid()` (4×4, n=50) in `matching.py` |
| 2026-05-30 | P1.6 | Added StabStitch trajectory smoothness λ=0.10 to `bundle_adjust.py` |
| 2026-05-30 | P1.7 | Auto-MFSR gate at Laplacian variance < 20 in `pipeline.py` |
| 2026-05-30 | P1.8 | Auto-inpaint gate at coverage < 0.95 in `pipeline.py` |
| 2026-05-30 | P1.9 | Midplane projection shift in `pipeline.py` Stage 9 |
| 2026-05-30 | P2.3 | `models/aliked_lg_wrapper.py` + Attempt 1b in `matching.py` + wired in `pipeline.py` |
| 2026-05-30 | P1.3 | `confidence_weights` param in `_render_median` + `_render`; per-frame confs computed from edges in `pipeline.py` |
| 2026-05-30 | P1.4 | `models/efficient_loftr_wrapper.py` (HF transformers); pipeline prefers EfficientLoFTR → LoFTR fallback; `yacs` installed |
