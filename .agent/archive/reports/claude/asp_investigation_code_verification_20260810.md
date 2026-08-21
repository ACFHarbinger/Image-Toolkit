# ASP Investigation — Code-Level Verification (companion to Grok's report)

**Author:** Claude (Code) · **Date:** 2026-08-10
**Relates to:** `.agent/reports/grok/asp_investigation_tests01_18_20260810.md`
(the primary ASP-investigation deliverable — read that first). This is a
focused verification pass over the specific source citations that report's
P0 recommendation depends on, plus one finding that changes the shape of the
fix.

## 1. Verified accurate

Spot-checked against `submodules/ASP/backend/src/rendering/compositing/_flags.py`:

| Flag | Report claim | Actual default | Match |
| --- | --- | --- | --- |
| `ASP_PHASE_COMPOSITE` | default OFF | `os.environ.get(..., "0")` | ✅ |
| `ASP_FG_REGISTER` | default ON | `os.environ.get(..., "1")` | ✅ |
| `ASP_GRAPHCUT_SEAM` | default OFF | `os.environ.get(..., "0")` | ✅ |
| `ASP_BLOCKS_GAIN_COMP` | default ON | `os.environ.get(..., "1")` | ✅ |
| `ASP_POST_SEAM_WARN_THRESH` | 8.0 | `"8.0"` | ✅ |

Gain clamps in `_photometric_stage.py`: confirmed `(0.80, 1.25)` and
`(0.88, 1.14)` exactly as cited — with one detail worth adding: the choice
between the two ranges is itself adaptive, `(0.80, 1.25) if _ref_lum_scalar
< 80.0 else (0.88, 1.14)` (line 59) — i.e. dark backgrounds get a wider
(more permissive) clamp than bright ones. Worth including in experiment E1's
design: the photometric-off A/B should control for which clamp regime each
test case was in, since it's not one fixed clamp.

## 2. Correction/refinement: where the SCANS-relative gates actually live

The report's §4.5 cites `seam_vis_gate` / `composite_gate_sb` as pipeline
gates. **They're real and I found their exact implementation** — but they
live in `backend/benchmark/bench_anime_stitch.py` (`CompositeGate`,
`GhostGate`/siqe, `SeamVisGate`, lines ~1880–2013), **not** in
`backend/src/`. I grepped for their implementing functions
(`_seam_coherence`, `_ghosting_score_v2`, `_seam_visibility_score`,
`CompositeGate`, `SeamVisGate`, `GhostGate`) across `backend/src/` and the
`gui/` tree: **zero matches outside the benchmark script and
`eval_dispatch.py`** (which is the human-rating tool, itself downstream of
benchmark output).

**This means the production pipeline (`backend/src/core/pipeline/run_stage.py`,
what the GUI actually calls) has no equivalent of these gates.** What it does
have — verified by reading `run_stage.py` directly — is a set of *pre-render*
sanity checks that fall back to SCANS: edge-graph connectivity (§1.15),
affine validation (Stage 7b), a `dy_cv` pre-detection gate (§4.7), an
alignment-stability gate (Stage 9.5), and a canvas-coverage gate (Stage 10.5).
All of these inspect the *input geometry* before rendering. **None of them
look at the final composite** — which is exactly the gap that would explain
why 06/12/15 render a geometrically "healthy" (per `affine_health.valid=True`,
noted in Grok's §3) but visually catastrophic composite: nothing downstream
of the geometry stage ever checks the rendered pixels.

**Practical implication for the P0 recommendation**: "expand recall on the
fallback gate" undersells the fix. There currently *is no* fallback gate on
rendered-output quality in the shipped pipeline — `CompositeGate`/
`GhostGate`/`SeamVisGate` are benchmark-only instrumentation used to compute
`render_gate_fallback` for scoring, not a safeguard a real user's stitch run
goes through. **Porting these three checks from `bench_anime_stitch.py` into
`run_stage.py`'s actual accept path (after Stage 10.5, before the final
`return`) is closer to the real P0 fix than tuning existing thresholds.**

## 3. One more concrete, checkable data point

`_SEAM_VIS_ABS_FLOOR` has an explicit calibration comment (line ~1975):

> "Floor calibrated 2026-07-09: the gate's motivating failures (test74=92.6,
> test34=62.8, test12=38.2) all exceed 35, while the S160 corpus ASP average
> (25.8) must not auto-fallback — a floor of 20 silently replaced most ASP
> output with SCANS."

So the floor was **deliberately raised from 20 to 35** on 2026-07-09 — with
test12 (one of Harbinger's catastrophic cases: human ASP=0) cited as one of
the *motivating* failures for having a gate at all, at sv=38.2, just barely
above the raised floor. If test12's benchmark-run `seam_visibility` score for
*this specific rating pass* comes in anywhere close to 35 (not 38.2 — that
number is from a different, larger 97-test corpus run, may not match this
session's run), it could be right at the edge of firing or not, which would
make the recall problem partly a threshold-tuning issue, not purely a
missing-gate issue for that specific case. Worth an experiment: **re-run the
benchmark for 06/12/15 with `ASP_GATE_SEAM_VIS_FLOOR` temporarily lowered to
20 (the pre-2026-07-09 value) and see whether that alone would have caught
them** — cheaper first experiment than E4 in Grok's report, and tells us
whether this is a threshold problem or a "gate doesn't exist in production"
problem (both are likely true to different degrees, but this test isolates
the threshold piece).

## 4. What I'd add to Grok's "Concrete experiments" table

| ID | Experiment | Tests | Success |
| --- | --- | --- | --- |
| E0 | Re-run `SeamVisGate`/`CompositeGate`/`GhostGate` (from `bench_anime_stitch.py`, unmodified) against 06/12/15's *actual rendered composite* for this session's run, with floor temporarily reverted to 20 | 06,12,15 | Tells us if this is a threshold problem (gate exists, mistuned) vs. a missing-safeguard problem (gate exists but isn't in the shipped path) |
| E7 | Port `CompositeGate`/`GhostGate`/`SeamVisGate` from the benchmark script into `run_stage.py`'s real accept path | 06,12,15 + full regression on 01–18 | Production pipeline itself falls back to SCANS on these, not just the benchmark's scoring of them |
