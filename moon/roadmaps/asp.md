# ASP Roadmap — Match or Exceed the OpenCV Stitcher on Every Benchmark Test

*Created 2026-07-09, immediately after the S200 great trim and the post-trim full
benchmark. Supersedes the retired 3,596-line roadmap (kept at `archive/moon/asp.md`
for reference — read it as a catalogue of what was already tried, not as a plan).*

**Objective.** For all 97 benchmark tests, the ASP output should be at least as good
as the OpenCV SCANS simple stitch — *as judged by a human* — and better on the
dimensions where the ASP is architecturally advantaged (coverage/framing, sub-pixel
sharpness, absence of periodic banding). "At least as good" explicitly includes the
coherence guarantee: the ASP must never lose a test by producing torn anatomy,
duplicated strips, or misordered content.

**Starting position (2026-07-09 baseline, `anime_stitch_20260709_030853.json`):**
27 asp_better / 41 comparable / 29 simple_better; aligned GT-SSIM 0.693 vs 0.718;
51 true composites + 46 guarded fallbacks; 87 s/test. The composite-quality wall is
frame-selection pose gaps (documented since June and still true). Authoritative
state: `.agent/cache/asp_state_of_the_pipeline.md` + `asp_benchmark_2026-07.md`;
strategy rationale: `research/ASP_Critical_Evaluation_2026-07-08.md` (§9); research
base: `research/Image_Stitching_Research.md` (the consolidated field reference) and
`research/ASP_Comprehensive_Research_Report.md` (algorithm specs, decision
thresholds, datasets) — see §R below for the distilled results this plan builds on.

---

## Ground Rules (carried from the critical evaluation — non-negotiable)

1. **One change → one benchmark → keep or revert.** 5-test verify
   (`just asp-benchmark-verify`) per change; full 97 (`just asp-benchmark`, ~2.5 h)
   before any default flips. Record the JSON filename in the item when done.
2. **Human visual verdict outranks every metric.** No item is "done" on SSIM alone;
   side-by-side montages (ASP | simple | Overmix | GT) are part of the definition of
   done. No automated metric currently measures structural coherence.
3. **Budgets:** ≤ ~50 env flags, ≤ 10 gates (a new gate displaces an old one),
   roadmap ≤ ~350 lines. Shipped items move to `docs/CHANGELOG.md`; failures get a
   one-paragraph post-mortem in `.agent/cache/asp_benchmark_*.md` — they do not
   accrete here.
4. **The human owns priorities and quality calls; agents implement and measure.**

**⚠ Benchmark host-freeze — likely fixed 2026-07-27, not fully re-verified.**
`bench_anime_stitch.py` repeatedly froze the host; root cause found (uncapped
OpenMP/BLAS/OpenCV/PyTorch thread pools) and fixed (capped to 4 threads) —
see 2.6 below. One clean 5-test run confirms the fix at that scale. **Prefer
small-to-moderate batches and watch system resources during any run larger
than previously tested** until a full-corpus run has confirmed it holds at
scale.

---

## §R — Research Base (already established; do not re-survey)

The two research reports in `research/` were written against this exact problem and
remain valid. Their load-bearing results, so future sessions build on them instead
of re-searching:

**Established and shipped (still in the trimmed core):** translation/affine-only
geometry (homography/APAP provably ill-conditioned on flat cels — rank-deficiency
argument, `Image_Stitching_Research.md §2–3`); the matcher recipe EfficientLoFTR →
ALIKED+LightGlue → template/phase-correlation → RoMa (§4); GNC-TLS bundle
adjustment (Yang 2020, 70–80 % outlier tolerance, μ-anneal /1.4); BiRefNet masking;
A5 fg-excluded median; ARAP Push→Regularise (Sýkora 2009) + symmetric midpoint warp
(StabStitch++ principle); A6 single-pose escalation (Eden 2006).

**The master principle** (research §8/§20, now proven twice by our own benchmarks):
*never average two conflicting poses — warp to agreement or select one; a skipped
frame beats a torn average.* Phase 2 below is this principle promoted to policy.

**Vetted-but-unused results to draw from (with their report anchors):**
- *Flow:* SEA-RAFT fine-tuned on **LinkTo-Anime** (2506.02733; cel-rendered GT
  flow) for flat-cel aperture failures; AnimeInterp **SGM** segment-level flow as
  the non-ML alternative; cross-validate any LinkTo-Anime training on **ATD-12K**
  (domain gap: 3-D-rendered vs hand-drawn — report §21.3).
- *Masking:* **ToonOut** (BiRefNet fine-tune, 95.3 → 99.5 % anime pixel accuracy)
  as a drop-in weights upgrade; **SAM-2** only after the 20-clip validation gate
  (report §21.1) — it is not officially benchmarked on anime.
- *Pose similarity for selection:* DWPose/ViTPose joint embeddings or fg-only flow
  magnitude — the background-confounded gradient metric is a documented failure.
  ConvGRU is a non-transformer flow-refinement alternative, worth a look only if
  SEA-RAFT/SGM both underperform.
- *Photometric:* Brown–Lowe joint gain (the §3.1 blocks solve below is its full
  form); **reverse-dimming** (Harding flash-test dimming is real in broadcast
  sources — `anime-undimmer`); region-stratified Reinhard or trapped-ball palette
  harmonisation (Hungarian match in Lab) instead of continuous colour transfer.
- *Seam:* graph-cut with hard t-link constraints is the *correct formalism* for
  single-pose regions (Eden 2006/Boykov–Jolly — our §4.2 failure was wiring, not
  theory); anime rule: weight seam cost by `(1 − edge_strength)` so seams run
  *along* strong line-art, not across flat fills; **DSeam** for speed if graph-cut
  returns; Intelligent Scissors is superseded by graph-cut, not worth building
  separately. **OBJ-GSP + SemanticStitch** (mesh-based, character-aware seam
  barrier) is a structurally different formalism — parked as a Phase-5 stretch
  candidate, not a Phase-1/3 alternative, since it's a new dependency class.
- *Blending:* **Modified Poisson Blending + MTOR** fixes the colour-bleeding that
  ruled out plain Poisson on flat cels; multi-band remains the default choice.
- *Datasets:* ATD-12K, AnimeRun, LinkTo-Anime, PaintBucket-Character, Sakuga-42M
  (report §22) — for any fine-tuning experiment.

**Do NOT adopt (report §21.2, plus trim-era additions):** UDIS++/SRStitcher
wholesale (natural-photo priors); VidPanos for bg completion (hallucination risk —
prefer ProPainter if bg completion returns); warp α > 0.5 on raw flow (test27
0.709 → 0.558); fg bbox crop without scroll-axis awareness; mpdecimate for anime
telecine; ToonCrafter without an LPIPS/CLIP quality gate (non-deterministic by its
authors' own warning). Overmix is GPL-3.0: run it as an external tool, re-implement
ideas clean-room, never link.

---

## Phase 0 — Measurement Foundation *(everything else depends on this)*

### 0.1 Human coherence ratings for the current baseline  `[HUMAN, ~45 min]`
Rate all 97 post-trim outputs (plus the simple stitches) 0–4 on structural
coherence: 4 = keepable, 2 = flawed but parses, 0 = incoherent. Store as
`data/human_ratings/asp_ratings_YYYYMMDD.json` (`{test: {asp: n, simple: n, notes}}`).
A tiny helper script that shows each montage and records a keypress is a 30-minute
build. **This is the metric the objective is defined against.**

### 0.2 Coherence-aware verdicts  `[1 day]`
- Add `human_coherence_asp/simple` columns to the benchmark JSON/report when a
  ratings file exists; the verdict may not report `asp_better` when the ASP
  coherence rating is below the simple stitch's.
- Calibrate the 12 automated metrics against the ratings (rank correlation per
  metric); demote anything that disagrees with humans on ranking to
  "diagnostic-only" in the report. This closes the test84/test53/test07 class of
  false `asp_better` verdicts for good.

### 0.3 Overmix as a third comparator on the full corpus  `[2–4 days]`
The benchmark currently compares against one competitor. Add Overmix:
- Build Overmix from source (github.com/spillerrec/Overmix, GPL-3.0 — run as an
  external tool, never link). It has a CLI (`OvermixCli`) suitable for scripting.
- Script `backend/benchmark/run_overmix.py`: for each `dump/asp_testNN`, feed the
  *smart-selected* frames (same input the ASP gets) and also the *full* frame set
  (Overmix's maximal-ingestion philosophy wants all frames); save
  `output/overmix_stitch.png` + a variant log (aligner/renderer settings used).
- Add `metrics_overmix`, `overmix_path`, and GT columns to `_build_result` and the
  report; extend the verdict to a three-way comparison table (no change to the
  asp-vs-simple verdict semantics — Overmix is a reference column, not a gate).
- **Study output**: a short write-up in `.agent/cache/overmix_field_notes.md` —
  where Overmix wins/loses on our corpus, how its AnimationSeparator groups our
  frames, what settings mattered. This directly feeds Phase 2.

### 0.4 Kill the GT-coupling measurement bug  `[(c) done and verified 2026-07-27,
S218/S220; (a)/(b) still open]`
Every past frame-selection improvement was vetoed by GT-SSIM because the GT
panoramas were assembled from specific frame timings. Fix the measurement, not the
selection: score selection experiments by (a) human rating, (b) aligned-SSIM
*computed on the overlap of content actually present in both images*, and (c)
seam-band pose-residual statistics (mean `post_warp_diff` across seams — lower =
easier compositing). **(c) implemented**: `_composite_foreground` already
collected `seam_post_diffs` internally (via `seam_meta_out`) but nothing read
it; the benchmark now passes `seam_meta_out={}`, computes the mean excluding
single-pose-escalation sentinels (phase-boundary/user-override, which aren't a
measured warp residual), and surfaces it as `"mean_post_warp_diff"` in the JSON
and a report line. **Verified (S220)**: values are stable and near-identical
between an `ASP_BG_AVERAGE` A/B (11.71→11.69, 13.51→13.35, 2.91→2.91, etc.) —
correctly orthogonal to a flag that only touches background rendering, not
foreground seam registration. (a) and (b) remain open — (a) needs the Phase
0.1 rating tool built first; (b) needs someone to actually change the
aligned-SSIM windowing logic. Optional (d): SI-FID as a reference-free signal
for non-GT tests — still unbuilt, only worth it if (a)+(c) leave those tests
hard to rank.

### 0.5 Optional second reference: Hugin  `[1 day, optional]`
`hugin` CLI tools (`pto_gen`/`cpfind`/`autooptimiser`/`nona`/`enblend`) can batch
scan-mode panoramas. Worth one afternoon to script on the 5-test subset; only roll
out to the full corpus if its outputs are competitive (expected: it struggles on
anime texture like all SIFT-based tools — confirming that is itself useful data).

**Phase-0 exit gate:** ratings file exists; benchmark emits coherence + pose-residual
columns; Overmix column present for all 97; a three-way summary table in the report.

---

## Phase 1 — Targeted Information Gathering *(parallel with Phase 0)*

### 1.1 Literature sweep — updates since the reports, not a re-survey  `[2–3 days reading]`
`research/Image_Stitching_Research.md` (consolidated 2026-06) already covers the
field through mid-2026; search only for what postdates or fills its gaps, and
append findings to that report so it stays the single reference:
- **Animation-phase clustering:** the reports cover hold detection (FD-Means,
  dHash) and Overmix's AnimationSeparator but no dedicated phase-clustering
  literature — search "animation cel phase detection", "cartoon keyframe
  clustering", "inbetweening detection". This is the one genuinely uncovered topic.
- **Anime optical flow after LinkTo-Anime (2506.02733):** released fine-tuned
  RAFT/SEA-RAFT checkpoints usable off the shelf; AnimeRun successors. (If a
  public cel-tuned checkpoint exists, it replaces our own fine-tune plans.)
- **Joint seam + exposure optimization:** the reports treat seam finding (§11) and
  gain (§9) separately, and our GraphCut measurement showed exactly that split
  failing — search for joint formulations (seam-cut energy with photometric terms).
- **Ghost-free fusion for dynamic scenes, 2024+:** the reports cite DDFNet/FDAN/
  SMURF as the flow→warp→fuse ancestry; look for pick-one-source attention fusion
  that maps onto phase-consistent reconstruction (2.3).
- **Pose-conditioned generative inbetweening:** ToonCrafter successors — reading
  only; the report's caveat stands (non-deterministic; mandatory quality gate),
  and no implementation happens until the Phase-2 core wins.

### 1.2 Overmix deep-dive (hands-on, pairs with 0.3)  `[with 0.3]`
Specifically answer: (a) how does `AnimationSeparator`'s error-threshold
change-point behave on hentai pan shots with 2–4 animation phases? (b) does its
average-render on *our* bg regions beat our temporal median visually? (c) what does
its interactive workflow do that our HITL checkpoints don't? Feed answers into 2.1.

### 1.3 GraphCut post-mortem experiment  `[2 days, flag-gated]`
§4.2 lost its first measurement (sv 20–80 vs DP 2–16) for identifiable reasons:
hard ownership cut, ±8 px feather, no per-seam photometric correction. The theory
is not in question — graph-cut with hard t-links is the report-endorsed formalism
for single-pose seam routing (§R; Eden 2006) — the wiring is. Before abandoning:
add per-boundary blocks-gain correction + distance-transform feathering (or reuse
the DP path's Laplacian blend along GC boundaries), apply the anime edge rule
(cost ∝ 1 − edge_strength so seams follow line-art), behind `ASP_GRAPHCUT_SEAM=1`;
re-run the 5-test verify. Keep only if it beats the DP path on both sv *and* human
rating; otherwise write the post-mortem and stop. (DSeam is the report-flagged
fast alternative if quality wins but runtime hurts.)

---

## Phase 2 — Coherence-First Core (the actual quality plan)

*Rationale: the simple stitch wins because adjacent frames ⇒ `A_animation ≈ 0`.
Give the ASP the same property via animation-phase awareness, instead of trying to
warp incompatible poses together. Evaluation §9.2 has the full sketch.*

### 2.1 `ASP_HOLD_AVERAGE=1` A/B  `[engineering done 2026-07-25/26, S214;
measured at full-corpus scale in S217]`
Overmix-style ECC sub-pixel averaging within hold blocks (§3.12A, never
measured) needed real engineering before it could even be measured: the
benchmark (`bench_anime_stitch.py`) carried its own older reimplementation of
frame selection that never called `frame_selection.py`, so the flag was wired
into code the suite never ran. Consolidated onto one implementation (S214);
fixed `_hold_block_average` (operated on thumbnails, discarded the averaged
pixels — never reached the final composite) and a hold-detector false
positive (slow scrolls misread as one giant hold, collapsing selection to
1–2 frames) by capping skippable hold-block size to plausible on-twos/threes
(≤8 frames). Both bugs pre-date this session and already affected the GUI
stitch path (`video_ingestion.py`), not just the benchmark. **S217 also
fixed the benchmark harness itself**: an uncaught `CanvasError` (SCANS
fallback failing on `asp_test10`) crashed the entire multi-hour batch with
zero results saved — the main loop now catches per-dataset exceptions and
checkpoints `results` to `output/_checkpoint.json` after every dataset, so a
killed run loses at most the in-flight one instead of everything.

5-test verify: neutral-to-slightly-better. **Full-corpus (S217, 2026-07-26,
n=96/97 — `asp_test10` fails even its SCANS fallback, a pre-existing edge
case this run surfaced)**, both this flag and 2.3's `ASP_PHASE_COMPOSITE=1`
run together (not isolated — host reliability cost too much for two more
full runs; numbers below are the combined effect, not attributed
individually) vs the 2026-07-09 baseline (n=97): CV verdict 31 asp_better /
36 comparable / 27 simple_better / 2 insufficient (was 27/41/29/0); aligned
GT-SSIM 0.694 vs 0.719 (was 0.693 vs 0.718 — flat, as expected: these are
seam/frame preprocessing wins, not the pose-gap architecture fix Phase 2.4
targets); sharpness 93.2 vs 59.8 (ASP +56%); ghosting_siqe 53.8 vs 72.4 (ASP
−26%); 44/96 guarded fallbacks (was 46/97). Net: more clear wins, fewer
losses, stronger secondary metrics, flat coherence proxy — real and
non-regressive, not the breakthrough Phase 2.4 targets. **Both flags stay
default OFF** regardless — the ground rules require a human visual pass
before "done," and none has run yet; these numbers justify prioritizing it.

### 2.2 Animation-phase grouping at ingestion  `[engineering done 2026-07-26, S215;
measured at full-corpus scale in S217 — see 2.1's numbers]`
`detect_animation_phases()` + `phase_spans()` added to `ingestion/frame_selection.py`:
pairwise dHash Hamming distance between consecutive *selected* frames, phase
boundary declared where the distance is a robust outlier (median + 2·MAD-sigma) —
the same primitive as hold detection (§3.4A) one level up. Wired into the
benchmark only for now (measurement — production `phase_ids` plumbing is 2.3's
job, once there's a consumer): diagnostics land in the JSON (`"phases":
{"count", "spans"}`) and a frame-strip-colored-by-phase PNG
(`animation_phases.png`) in both the per-test plots dir and the markdown report.
**Confirmed zero behavior change** on the 5-test verify (composite metrics
byte-identical to the pre-2.2 baseline). Full-corpus phase census (S217,
n=96): 1–6 phases/test, mean 2.18, 60/96 tests had more than one phase —
i.e. most tests genuinely have the multi-phase structure 2.3 targets, this
isn't a rare case.

### 2.3 Phase-consistent compositing  `[engineering done 2026-07-26, S216;
measured at full-corpus scale in S217 — see 2.1's numbers; human ratings
(the actual success criterion) still pending]`
`ASP_PHASE_COMPOSITE=1` (default OFF): `_check_preemptive_escalations` in
`compositing.py` now checks, before any registration attempt, whether a
seam's two frames belong to different phases; if so it skips midpoint-warp
entirely and escalates straight to single-pose from the dominant (more-
complete) phase, via the dominant-frame-in-band logic the user-override path
already used (extracted into `_dominant_frame_in_band`). ARAP midpoint warp
untouched for within-phase seams. `phase_ids` computed once per run in
`AnimeStitchPipeline.run()` (shared by GUI and benchmark — learned from 2.1,
no separate reimplementation this time), **after** every frame-dropping
dedup pass so indices stay aligned (an early draft computed it before dedup
and would have silently desynced — caught before shipping).

5-test verify: neutral-to-slightly-better; 8 seams hit a phase boundary and
correctly escalated; `asp_test04` spot-checked visually — coherent, no
tearing. Full-corpus (S217, combined with 2.1's flag, n=96): see 2.1's
numbers for the aggregate delta. Human ratings — the roadmap's actual
Phase-2.3 success criterion ("zero coherence-class losses among true
composites" needs eyes on images, not SSIM) — have not run; that's the
next step before either flag can flip to default-on.

### 2.4 Phase-aware frame selection  `[1 week, after 2.2 metrics]`
Bias `smart_select_frames` to take camera-step candidates from the *same* phase
when possible (the on-twos/threes exploitation that failed in S3/S8 for
measurement reasons — now unblocked by 0.4). Phase membership from 2.2 *is* the
pose-similarity metric the reports called for (§R: background-agnostic, unlike the
failed gradient metric; cheaper than DWPose/ViTPose embeddings, which remain the
upgrade path if phase granularity proves too coarse). Success metric: mean seam
`post_warp_diff` drops; human ratings don't regress.

### 2.5 Background quality: Overmix-style averaging  `[MEASURED HARMFUL,
2026-07-27, S220 — keep default OFF, do not re-enable without a real fix]`
`ASP_BG_AVERAGE=1` (default OFF) in `rendering.py`: where ≥3 frames agree a
canvas pixel is confirmed-background, the per-pixel temporal median is
replaced with the mean for √N noise reduction. **5-test verify result**:
sharpness/ghosting metrics improved substantially (sharpness_asp 119.9→148.4,
ghosting_siqe 49.6→39.2) and one previously-fallback test (`asp_test04`)
started producing a true composite instead of falling back to SCANS — but
**visually inspecting that composite shows clear horizontal strip-banding
artifacts** (luminance/hue jumps between strips, especially visible on the
right side of the frame). This is exactly the "never trust a metric without
looking at the image" case the ground rules warn about — the improved
sharpness/ghosting numbers came from a *worse*, more visibly broken
composite, not a better one. Likely cause: the abrupt switch between mean
(count≥3) and median (count==2) creates a visible discontinuity exactly at
the count boundary between adjacent canvas strips, and/or averaging across
frames with residual exposure differences the median was implicitly masking
by picking one sample. **Not worth pursuing further without addressing the
strip-boundary discontinuity directly** (e.g. blend mean/median smoothly
across the transition zone, or a per-strip gain-matched mean) — flag stays
OFF; this item should not be re-attempted as-is.

**Phase-2 exit gate:** on the 55-GT subset, ASP human coherence ≥ simple on every
test; aligned-SSIM gap ≤ 0. (Coverage wins like test96 should start flipping
`comparable` → `asp_better` once coherence losses stop cancelling them.)

---

## Phase 2.6 — Benchmark-Harness Host Freeze *(likely fixed 2026-07-27,
S218/S219/S220 — re-verify at scale before fully trusting)*

`bench_anime_stitch.py` repeatedly froze the host badly enough to force a
hard restart (2026-07-25 through 2026-07-27), on a 128GB RAM / 24GB VRAM
machine — a real bug, not underpowered hardware. **Root cause**: the user
noticed many concurrent processes/threads in `htop`; code audit found nothing
in the codebase ever capped OpenMP/BLAS/OpenCV/PyTorch thread pools, so each
defaulted to one thread per CPU core independently, stacking uncoordinated on
a high-core-count machine (numpy BLAS, OpenCV `parallel_for_`, PyTorch
intraop, and the C++ `base` extension's own `#pragma omp parallel for` in
`canvas.cpp`). **Fix**: `OMP_NUM_THREADS`/`OPENBLAS_NUM_THREADS`/
`MKL_NUM_THREADS`/`NUMEXPR_NUM_THREADS` capped to 4 (`ASP_BENCH_THREAD_CAP`)
before numpy/cv2/torch import, plus explicit `cv2.setNumThreads`/
`torch.set_num_threads`. **Confirmed**: the exact 5-test combination that
previously froze the host completed cleanly with the fix — RSS/RAM/VRAM flat
and bounded across all 5 datasets, benchmark-process thread count settled at
22–34 (not growing) versus unbounded before. Also added (kept as permanent
diagnostics): `_resource_snapshot()`/`_resource_danger()` abort guardrail
(RAM≥80%/VRAM≥85%) and `_log_resource(tag)` per-stage checkpoints inside
`process_dataset`. Note: both the in-process guardrail and an external bash
watchdog *failed* to prevent one freeze before the thread-cap fix — automated
safety nets alone aren't sufficient; the thread cap is the actual fix, not
the monitoring.

**Only one confirmed clean run (5 tests) exists post-fix.** Before trusting
this fully: re-verify at larger scale (10–20 tests, then full corpus),
ideally with the user watching system resources live, since the original
freezes happened at varying scales. If a freeze recurs, lower
`ASP_BENCH_THREAD_CAP` further, and audit the remaining `base` C++ files not
yet checked for memory safety (`frame_selection.cpp`, `fg_register.cpp`,
`compositing.cpp`, `seam.cpp`, `exposure.cpp` — `canvas.cpp` was checked and
is clean) and the model-wrapper `.offload()` paths (BiRefNet caches by
`(model_name, device)` and is reused; LoFTR has no such cache and reloads
fresh every dataset — a plausible fragmentation source, still unconfirmed).

## Phase 3 — Photometric & Seam Parity with OpenCV

*(Only after Phase 2 — these polish composites that must first be coherent.)*

- **3.1 Joint canvas-space blocks-gain solve** `[1 week]` — the full Brown–Lowe
  2007 formulation (research §9.3): one least-squares system over all frame pairs'
  overlap blocks with a gain-prior term (current §4.10 is sequential pairwise;
  drifts over long chains). Bg-pixels-only, luminance-scalar, clamped — the
  report's empirically-derived anime rules. Targets the residual banding
  (composite_gate_sb fires on 19 tests).
- **3.2 GraphCut revisit** — inherit from 1.3 if it survived.
- **3.3 Multi-band blend on final boundaries** `[3 days]` — only if 3.1+3.2 leave
  visible transitions; reintroduce the deleted C++ `multiband_blend` at that
  point, not before. If flat-cel colour bleeding appears at high-contrast seams,
  the report's answer is **MPB + MTOR** (modified Poisson, §12), not plain Poisson.
- **3.4 Cheap photometric candidates from the research base** `[1–2 days each,
  A/B'd individually]` — **ToonOut weights** for BiRefNet (pure weights swap, but
  note the MatteoKartoon HF repo is gone — locate a mirror first); **reverse
  dimming** for broadcast-dimmed sources (per-frame luminance restore before
  registration, research §9.1) — check whether any of the 97 tests actually show
  Harding dimming before building it.

---

## Phase 4 — Convert the Fallback Classes

The 46 guarded fallbacks are wins-by-safety, not wins. Reclassify each:
- **seam_vis_gate class (24):** should shrink substantially via 2.3 (their failed
  composites are mostly pose-blend artifacts). Re-examine what remains.
- **render-gate class (21):** fg-dominant high-animation scenes where multi-frame
  assembly may be structurally wrong. For these, a *deliberate* policy: best
  single-phase reconstruction (2.3 degenerate case) vs SCANS — pick per-test by
  measurement. Accepting SCANS permanently for some tests is a valid outcome **if
  a human confirms SCANS is the best achievable** — the objective is "never worse
  than the OpenCV stitcher", which a coherent fallback satisfies; but each such
  test must beat the *raw* cv2 stitcher (our SCANS-on-preprocessed-frames already
  tends to, via selection + photometric prep + no crop failures).
- **alignment_failed (test49):** one test; diagnose individually.

**Phase-4 exit gate = the objective:** for every one of the 97 tests, ASP output
human-rated ≥ the simple stitch, with `asp_better` on the coverage/sharpness
dimensions wherever a true composite ships.

---

## Phase 5 — Exceed (stretch, unscheduled)

Only once Phases 0–4 hold: per-phase super-resolution output (Overmix's actual
specialty — √N sub-pixel averaging), optional Real-ESRGAN anime_6B or APISR finish
(the two report-vetted anime SR models, §15), GC/multi-band refinements, OBJ-GSP +
SemanticStitch mesh-based seam barrier as a third seam candidate (§R), and
revisiting generative seam synthesis with whatever 1.1 found — each as a measured
A/B, and any generative step behind the report-mandated LPIPS/CLIP quality gate.

---

## Parked (real gaps, explicitly deferred until the Phase-4 exit gate)

*Carried forward from the archived roadmap — these are engineering/research items
with unimplemented value that were never benchmarked or rejected, unlike the §5.x
gate factory. They are out of scope until every one of the 97 tests clears Phase 4,
but should stay visible rather than silently vanish.*

- **Full 2D canvas geometry for horizontal/diagonal scroll** (Category F/H in the
  archived taxonomy). Non-vertical scroll only gates to SCANS today; touches
  canvas/warp/seam code that assumes 1D vertical layout — high blast radius,
  multi-week, do not start before Phase 4.
- **StabStitch++ multi-axis trajectory smoothing** — wave correction is linear
  today (`np.polyfit` deg=1, §4.3); pairs naturally with the 2D-canvas item above,
  probably not worth doing alone.
- **HITL manual-correction primitives** (Fourier-Mellin manual align, arrow-based
  flow override). The evaluation credits Overmix's interactive workflow as good
  product design (§8); revisit only if Phase 2's automated compositing leaves a
  test class no automated policy can resolve.
- **ASP → HybridStitch handoff** — integration into the main app's general stitch
  tab, once quality no longer needs the benchmark harness to validate every change.

---

## Anti-Goals (do not do these; the archive documents why)

- No new quality gates or per-strip/per-seam statistics without a displaced gate
  and a full-corpus run (§5.x factory, 104 items, zero measured value).
- No threshold-tuning sessions (±0.002 SSIM outcomes, weeks lost).
- No new default-OFF flags "for later" — implement behind a flag only with the
  A/B run scheduled in the same session.
- No Phase-2-era ambitions (video ingestion, dataset harvesting, RLHF, 4K hybrid)
  until the Phase-4 exit gate is met.
- No trusting `asp_better` without looking at the image.
