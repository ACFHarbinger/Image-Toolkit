# ASP Investigation Report — Human Ratings Tests 01–18

**Author:** Grok (Build) · **Team:** ASP investigation  
**Date:** 2026-08-10  
**Evidence:** `submodules/ASP/data/benchmarks/asp_evaluations_20260810.json` (18 tests, first pass by ACFHarbinger) correlated with automated run `anime_stitch_20260807_045552.json`  
**Do not treat automated SSIM/sharpness as human coherence.**

---

## 1. Executive summary

Across **asp_test01–asp_test18**:

| Metric | Value |
| --- | --- |
| Mean human ASP | **2.00** / 4 |
| Mean human Simple (SCANS) | **3.39** / 4 |
| Preference | **simple 14** · **tie 4** · **asp 0** |
| ASP never preferred once in this window | |

Harbinger’s qualitative call is confirmed by the structured scores: **SCANS usually shows mild ghosting; ASP shows banding, color shift, and hard seam lines**, with catastrophic cases (tests 06, 12, 15, and hard failures 07/14) featuring torn anatomy / misordered content / blown photometry.

**Key systems finding:** On most human-catastrophic cases, **`used_fallback` is False** — the pipeline **accepted** a bad ASP composite instead of handing off to SCANS. Conversely, when fallback *does* fire (`seam_vis_gate` / `composite_gate_sb`), SCANS often still wins human preference (fallback image may still be imperfect, or gate fires too late / wrong path). **Automated sharpness is frequently higher for ASP than SCANS even when humans rate ASP far worse** — optimizing sharpness/ghosting alone will not fix this.

---

## 2. Per-test scoreboard (human)

| Test | ASP | Simple | Pref | Top defects (ASP-side narrative) |
| --- | --- | --- | --- | --- |
| 01 | 3 | 4 | simple | crop_loss (both crop; SCANS less bad) |
| 02 | 2 | 3 | simple | color_shift (yellow cast), banding, seam over character, SCANS ghosting |
| 03 | 3 | 4 | simple | banding + seam color discontinuity; SCANS “perfect” |
| 04 | 1 | 3 | simple | torn anatomy + multi-defect; SCANS minor ghosting |
| 05 | 3 | 4 | simple | dark seams + color shift bottom |
| 06 | 1 | 4 | simple | **worst contrast early** — ASP top half “completely white”, dups, warp |
| 07 | 0 | 1 | tie | both insane; SCANS near single-frame; ASP composite nightmare |
| 08 | 3 | 4 | simple | ASP near-perfect edges; SCANS perfect; Hugin stretch note |
| 09 | 3 | 4 | tie | crop_loss / non-connecting edges on ASP |
| 10 | 4 | 4 | tie | both perfect (rare win-tie) |
| 11 | 2 | 3 | simple | color shift + extreme crop on ASP |
| 12 | 0 | 4 | simple | **most extreme** — SCANS near perfect, ASP “alien” |
| 13 | 2 | 2 | tie | same structural failures; **Hugin outlier good** |
| 14 | 0 | 1 | simple | ASP full defect set; SCANS slightly better but still broken |
| 15 | 1 | 4 | simple | SCANS pixel-perfect; ASP reverse |
| 16 | 3 | 4 | simple | ghosting (ASP worse); Hugin stretch |
| 17 | 2 | 4 | simple | color shift + banding + seams |
| 18 | 3 | 4 | simple | high-contrast seams + ghosting |

**Defect frequency (tags on rated tests):**  
seam_line 11 · color_shift 10 · banding 9 · ghosting 8 · crop_loss 7 · torn_anatomy 7 · misordered_content 6 · duplicated_strip 6 · blur 5 · geometry_warp 4

**Worst human gaps (simple − asp):**  
12 (+4) · 06 (+3) · 15 (+3) · 04 (+2) · 17 (+2)

---

## 3. Correlation with automated run (20260807 full corpus)

For tests 01–18 (same IDs in automated dump):

| Pattern | Observation |
| --- | --- |
| **Sharpness ASP > Simple** | True on **14/18** cases — including human disasters 04,06,12,15 |
| **Fallback used** | True on 7/18 — mostly `seam_vis_gate` or `composite_gate_sb` |
| **Fallback missed disasters** | **06, 12, 15, 04, 17** had `used_fallback=False` while human ASP ≤ 2 (and 06/12/15 ≤ 1) |
| **Fallback but still lose** | 01,08,09,11,13,16 — gate fired, human still prefers simple or ties |
| **Photometric gains** | Worst cases show wide `gain_range` clamped to ~**[0.8, 1.25]** with many frames at the clamp (e.g. test12: gains stuck at 0.8/1.25; test15: 28 frames corrected, same clamp) |

Example **test12** (human ASP 0 / Simple 4, no fallback):

- Affine health `valid: True` — geometry stage thinks it is fine.
- Photometric: large bg luminance swing (13→67), gains hard-clamped.
- Phases: 2 phases — pose/phase boundaries relevant to torn anatomy.
- Automated comparison: `verdict: simple_better` via ground_truth SSIM — agrees directionally, but sharpness still ASP≫Simple.

**Conclusion:** Gates and metrics are **not aligned with human structural failure**. Sharpness is actively **misleading** as a quality proxy for anime panoramas.

---

## 4. Likely root-cause families (code-linked)

Mapped to Harbinger defects → ASP code areas under `submodules/ASP/backend/src/`.

### 4.1 Color shift & global cast (defects: color_shift, “yellow infects whole image”)

| Source | Path / mechanism | Why it matches notes |
| --- | --- | --- |
| **Background photometric normalization** | `core/pipeline/_photometric_stage.py` | Per-frame BGR gain to median bg; clip **[0.80,1.25]** or **[0.88,1.14]**. Local lighting / non-uniform bg → wrong global cast (test02 yellow). |
| **Per-segment photometric (P2.6)** | same file | Segment match to frame-0 color can amplify wrong region pairing. |
| **Per-channel block gain** | `rendering/compositing/_gain_compensation.py` `_blocks_gain_compensate` | Explicitly known to cause **colour cast** when a channel mean is near zero; LAB L path exists (`_blocks_lum_compensate`) but BGR path may still run (`ASP_BLOCKS_GAIN_COMP` default ON in `_flags.py`). |
| **Gain clamp saturation** | photometric + joint gain | Clamped gains (0.8–1.25) on large luminance ranges → residual strip exposure steps → perceived banding/color seams. |

**Investigation next steps:**

1. Dump pre/post photometric frames for tests **02, 06, 12, 15, 17**.
2. A/B: disable stage 4.5 / 4.5b / blocks BGR gain independently; re-run those tests + human re-rate.
3. Prefer **LAB L-only** spatial gain (or chroma-preserving models) over per-channel BGR for anime flats.
4. Widen or adapt gain clamps based on actual bg luminance range, or use robust matching (median of ratios, not mean).

### 4.2 Banding & seam lines (defects: banding, seam_line)

| Source | Path / mechanism | Why it matches notes |
| --- | --- | --- |
| **Pairwise seam DP + feather** | `compositing/_seam_cut.py`, `_seam_cost.py`, `composite.py` | Visible seams when cost ignores large photometric residual or feather insufficient. |
| **GraphCut path (off by default)** | `_flags.py` `_GRAPHCUT_SEAM` | First measurement *worsened* seam_visibility; GC without matching photometry is known bad. |
| **Strip-level residual after global gain** | blocks gain §4.1 | Horizontal anime pans → strip banding exactly as described. |
| **Post-seam lum step audit** | `_flags.py` `_POST_SEAM_WARN_THRESH` | Warnings only; does not block accept. |

**Investigation next steps:**

1. Use existing `backend/benchmark/diagnose_seams.py` and `diagnose_seam_photometrics.py` on tests **02,03,05,17,18**.
2. Log per-seam mean |ΔL| and chroma Δ before accept; add **human-aligned gate** if ΔL or ΔE exceeds threshold in character bbox.
3. A/B feather width and multi-band blend vs current Laplacian path on worst seam cases.
4. Character-aware seam cost (penalize cuts through fg mask / BiRefNet) — notes stress seams **over the character**.

### 4.3 Torn anatomy / duplicates / misordered content

| Source | Path / mechanism | Why it matches notes |
| --- | --- | --- |
| **Phase mixing** | `_flags.py` `_PHASE_COMPOSITE` **default OFF** | Critical eval failure mode: body parts from two poses. Flag exists but not default — test12 has **2 phases**, test15 has **4**. |
| **FG pose registration** | `alignment/fg_register/`, `ASP_FG_REGISTER` default ON | Can help or hurt; need A/B on 04,06,12,13,15. |
| **Frame selection / span** | `frame_selection` in dataset JSON | Wrong spans → impossible geometry; SCANS simpler path survives. |
| **Affine “healthy” but content wrong** | `affine_health.valid=True` on disasters | Geometry acceptance ≠ semantic coherence. |

**Investigation next steps:**

1. Force `ASP_PHASE_COMPOSITE=1` on multiphase tests (12, 15, phase count ≥ 2); measure human + seam metrics.
2. Visualize phase spans vs composite ownership maps for 06/12/15.
3. Single-pose policy when phase change in overlap (document as product rule).
4. On test13, study **why Hugin wins** — different motion model / seam policy lessons for ASP.

### 4.4 Crop loss

Often both methods crop; ASP sometimes worse (01, 09, 11). Secondary to structure but affects “keepable” score.

**Next:** canvas / ROI selection audit; compare SCANS canvas to ASP canvas for same tests.

### 4.5 Fallback / product policy failure

| Gate | Behavior on 01–18 |
| --- | --- |
| `seam_vis_gate` | Fires on 01,08,09,10,13 — not on 06/12/15 disasters |
| `composite_gate_sb` | 11, 16 |
| No gate | Most human-worst cases |

**Hypothesis:** Seam visibility and composite scoreboards track **proxy metrics** (possibly related to sharpness/edge energy) that **do not** fire when the failure is global cast, white-out, or semantic chaos with still-high edge energy.

**Investigation next steps:**

1. Plot gate features vs human ASP score on 01–18; find thresholds that would have caught 06/12/15 without nuking 10.
2. Temporary product policy: **if human-proxy or multi-defect auto-tags fire → serve SCANS** for IT users while ASP remains research path.
3. Do not remove research ASP path; separate **“ship default”** vs **“experimental ASP”** in GUI.

---

## 5. Prioritized solution tracks (for ASP submodule)

### P0 — Stop shipping incoherent ASP as default

1. **Human-aligned accept gate** using combination of: seam ΔE/ΔL in fg, photometric residual energy, phase-boundary policy, optional cheap no-ref coherence heuristic.  
2. **Default to SCANS** when gate fails (already partially present; **expand recall** on 06/12/15 class).  
3. **Dashboard / CI:** never promote ASP on sharpness alone; require human batch or proxy that correlates with 01–18.

### P1 — Photometric correctness (color_shift, banding)

1. A/B matrix: photometric off / L-only / current / loosened clamps.  
2. Fix or demote per-channel BGR block gain on anime.  
3. Per-test photometric debug dumps in benchmark package.

### P2 — Seam quality (seam_line)

1. Character-aware seam cost.  
2. Feather / multi-band re-tune with human re-rate on 02,03,05,17,18.  
3. GraphCut only with matching photometry (keep default OFF until then).

### P3 — Motion / phase / anatomy (torn, duplicate, misordered)

1. Enable and measure `ASP_PHASE_COMPOSITE`.  
2. FG register A/B.  
3. Hugin win cases (13, 18 notes) as external teachers.

### P4 — Hard scenes (07, 14)

Both methods fail — dataset/scene class for “no automatic panorama” or multi-plane / user HITL, not only ASP tuning.

---

## 6. Concrete experiments (next engineering week)

| ID | Experiment | Tests | Success |
| --- | --- | --- | --- |
| E1 | Photometric stage off | 02,06,12,15,17 | Human ASP ≥ +1 or fewer color_shift tags |
| E2 | Blocks gain L-only / off | 02,03,05,17 | Fewer banding/seam color tags |
| E3 | `ASP_PHASE_COMPOSITE=1` | 12,15 | Less torn/misordered |
| E4 | Tighten fallback to catch 06/12/15 proxies | 06,12,15 + holdout 10 | Fallback True on disasters; still OK on 10 |
| E5 | Character-penalized seam cost | 02,05,18 | Seam not across character |
| E6 | Re-rate after each E* with `just asp-benchmark-assess --tests …` | subset | Document in evaluations JSON |

Commands:

```bash
# from Image-Toolkit root
just asp-benchmark-tests asp_test06 asp_test12 asp_test15
just asp-benchmark-assess --start-at asp_test06
just dashboard-data
```

---

## 7. What this means for Image-Toolkit product

- **Honest UI:** show SCANS as quality baseline; label ASP experimental until human mean ≥ SCANS on a frozen slice (e.g. 01–18 + verify suite).  
- **Docs/website:** ratings dashboard already separates human vs automated; keep that wall.  
- **Submodule ownership:** ASP needs a dedicated quality milestone driven by **this** evaluation file, not only automated `verdict_counts`.

---

## 8. Open questions for Harbinger

1. After full corpus, is **SCANS-default + ASP advanced toggle** acceptable for the IT GUI?  
2. Priority: fix **color/seam (common)** first, or **catastrophic anatomy (rare but damning)** first?  
3. Re-rate policy: full 01–18 after each experiment, or only worst 5 + verify suite?

---

## 9. Team note

This report is the ASP-investigation deliverable from Grok. Docs/website team should keep shipping dashboard/React work without blocking on ASP code changes; both consume the same evaluation JSON via `just dashboard-data`.
