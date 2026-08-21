# Anime-Stitch-Pipeline — Comprehensive Status Report

*Author: Claude (Fable 5), 2026-08-08. Written as an independent read of the ASP
submodule (`submodules/ASP`, commit `8eeeeac`) — code, docs, roadmap, benchmark
history, and agent-cache postmortems — treating ASP as a standalone desktop
application first and an Image-Toolkit submodule second.*

---

## 1. Executive Summary

ASP is a desktop application for stitching scrolling anime/manga capture frames
into a single panoramic image, with two surfaces: an automated ML pipeline
(`AnimeStitchPipeline`, 13 stages, C++ hot paths) and a manual interactive tool
(`HybridStitchPanel`, PySide6). It sits at a genuinely unusual maturity point:

- **Its measurement and process infrastructure is exceptional** — a 97-test
  benchmark corpus with 55 ground truths, four-way comparators (ASP / OpenCV
  SCANS / Overmix / Hugin), a purpose-built PySide6 rating inspector, a FiftyOne
  triage surface, ruthless postmortem culture, and non-negotiable ground rules
  ("one change → one benchmark → keep or revert"; "human verdict outranks every
  metric"). This is better evaluation discipline than most published research
  code.
- **Its core quality problem remains unsolved and has plateaued.** After ~280
  sessions across three-plus months, the automated pipeline still does not beat
  the OpenCV SCANS baseline on the corpus: the latest full run (2026-08-07,
  `anime_stitch_20260807_045552.json`) shows 22 asp_better / 53 comparable /
  22 simple_better, aligned GT-SSIM 0.666 vs 0.693, 43 true composites vs 54
  guarded fallbacks. These numbers are statistically identical to 2026-07-28.
- **The single blocking item is a ~45-minute human task** — the Phase 0.1 human
  coherence rating pass. Every measured-positive flag (`ASP_HOLD_AVERAGE`,
  `ASP_PHASE_COMPOSITE`, `ASP_POSE_WINDOW_PX`) is held default-OFF pending it.
  The tooling for it was rebuilt and verified weeks ago. Nothing in the quality
  track can legitimately move until it runs.
- **Recent work (2026-08-06/07) was overwhelmingly infrastructure repair**, and
  honest about it: packaging fixes (uv/CUDA, issue #5), justfile repair (#9,
  `just` had never successfully parsed), benchmark-harness measurement bugs
  (#10), two real pipeline bugs (#11, SAM-2 mask resize; #12, dead DINOv2
  helper), and a complete mypy/ruff cleanup (137→0 and 215→0 mypy errors in
  backend/gui respectively). Corpus-scale verification confirmed zero behavior
  change — which is both reassuring (discipline held) and sobering (the quality
  gap is untouched).

The honest overall verdict: **ASP is a well-run research project wearing the
clothes of a product that doesn't exist yet.** The artist-facing value today is
`HybridStitchPanel` plus onboarding (wizard, tutorials, bundled samples — all
shipped 2026-08-06/07); the automated pipeline is a strong research asset whose
default output an artist would keep less often than the OpenCV baseline's.

---

## 2. Product Framing

Stated purpose: a desktop app to edit and stitch anime-style cel-shaded images
into panoramas, using ML (DL/RL) and mathematical optimization (swarm,
evolutionary) to minimize artist effort, plus tutorials for beginners.

Current reality against that statement:

| Vision element | Status |
| --- | --- |
| Desktop app for stitching | ✅ Working (PySide6 `gui/`), but not packaged/distributable |
| Image editing tools | ✅ Partial — HybridStitchPanel: control points, color correct, seam painter, mesh warp, render |
| ML-assisted automation | ⚠️ Exists (13-stage pipeline) but loses to a non-ML baseline on the corpus |
| RL / swarm / evolutionary | ❌ Built pre-trim, deleted in the S200 "great trim" as unverified complexity; reintroduction bounded under Phase 5.1, gated behind Phase 4 exit |
| Tutorials for beginners | ✅ Shipped 2026-08-06/07: onboarding QWizard, two docs-site tutorials, three bundled sample sequences |
| Distribution (installers, model weights, GPU story) | ❌ Absent — SAM-2 checkpoint fetch undocumented/unautomated, CUDA extras needed for research matchers, no binary packaging |

There is an unresolved tension between two possible north stars:
1. **Autonomous-first**: the roadmap's objective — match/exceed OpenCV SCANS on
   all 97 tests, human-judged. Phase 4's exit gate blocks Phase 5 (ML/RL
   ambitions), 2D canvas work, the Tauri frontend, and more.
2. **Assistive-first**: the Overmix lesson the critical evaluation itself
   endorses ("human-in-the-loop as workflow, not checkpoint") and what
   `HybridStitchPanel` embodies — the automation proposes, the artist disposes.

The roadmap's §0 already resources both in parallel, but the exit-gate
structure still makes the autonomous benchmark the project's center of gravity.

---

## 3. Repository & Tech Stack

```
backend/   Python 3.11+ — pipeline orchestration, ingestion, model wrappers,
           alignment, rendering, benchmark/evaluation subsystem (~40k LOC total
           across backend+gui+base+frontend)
base/      C++17 + pybind11 — hot kernels: matching, bundle_adjust, canvas,
           seam, exposure, compositing, fg_register, frame_selection, validation
gui/       Python/PySide6 — Stitch tab (automated) + HybridStitchPanel (manual)
frontend/  Tauri/TypeScript scaffold — FROZEN (9-line main.ts), by explicit
           decision 2026-08-06
docs/      MkDocs + Sphinx + Structurizr + Doxygen/TypeDoc + hand-built Vue
           site (5 toolchains — flagged for consolidation, not yet done)
vendor/    (at Image-Toolkit level) EfficientLoFTR, JamMa, BiRefNet, ComfyUI,
           Hugin, OpenCV, Overmix forks
```

Key stack facts:
- Deps: numpy/opencv/scipy/skimage, torch/transformers/kornia, PySide6, av.
  Research matchers (SAM-2, ptlflow, romatch, mamba_ssm) correctly moved to an
  optional `matchers` extra (issue #5) after they broke `uv sync` on non-CUDA
  machines for an unknown length of time.
- The pipeline class is assembled from mixins (`_RunStageMixin`,
  `_MatcherSelectionMixin`, `_ThinWrappersMixin`) over implicit shared state,
  patched for type-checking with `TYPE_CHECKING`-only Protocols
  (`_PipelineHost`, `_StitchTabHost`). mypy is now clean (0 errors both
  packages) but the Protocol scaffolding is a symptom: state flows are implicit
  and the orchestrator (`run_stage.py`, ~676 lines) acknowledges in its own
  docstring that full decomposition needs "a stateful context object threaded
  through every stage."
- **Package-identity split**: `run_stage.py` imports from both `asp_backend.*`
  and `backend.src.*` in the same file. The top-level names `backend`/`gui`
  collide with Image-Toolkit's identically-named packages (issue #3), which
  keeps CI collection broken standalone and couples the submodule to the host
  repo's conftest/interpreter.
- README.md is entirely stale — it still describes the repo as "a GitHub
  template repository. It ships no product code of its own," with badges for
  seven languages and four build systems that don't apply. As a standalone
  project's front door, this is actively misleading.

## 4. The Automated Pipeline (13 stages, post-trim)

Spine (all default-ON): smart frame selection (greedy 50px displacement + hold
detection + blur/contrast rejection) → load/sort/width-normalise → BaSiC
flat-field → BiRefNet fg/bg masks (ToonOut weights — genuinely loading since
the 2026-07-27 triple-bug fix; they had *never* loaded before) → bg photometric
normalisation → matching cascade (EfficientLoFTR → kornia LoFTR →
ALIKED+LightGlue → template → phase-correlation → RoMa) → GNC-TLS bundle
adjustment → affine validation/retry → dy_cv gate → SEA-RAFT/ECC refine →
canvas + midplane → A5 fg-excluded temporal median → fg composite (per-seam
RAFT/DIS flow → ARAP → symmetric midpoint warp → A6 single-pose escalation →
DP seams → 5-band Laplacian blend) → trim/fill/crop/save.

Gate set: 8 (edge-graph connectivity, affine validation chain, dy_cv,
horizontal-scroll, multi-frame coverage, A6 escalation, bench CompositeGate,
bench Ghost/SeamVis gates). Budget-capped: a new gate must displace an old one.

Flag-gated experiments, all measured, all default-OFF awaiting human ratings:
- `ASP_HOLD_AVERAGE` (Overmix-style sub-pixel hold averaging): real,
  non-regressive full-corpus improvement in sharpness/ghosting.
- `ASP_PHASE_COMPOSITE` (phase-consistent seam escalation): neutral-to-better,
  the architectural centerpiece of the coherence-first plan.
- `ASP_POSE_WINDOW_PX=80` (DINOv2 pose-consistent selection): the only flag to
  ever produce an `asp_better` verdict flip on the verify subset; mixed
  metrics, needs eyes.
- `ASP_USE_SAM2`: honestly measurable since issue #11's fix; genuinely mixed
  (GT-SSIM worse, sharpness/ghosting better); stays OFF.
- `ASP_JOINT_GAIN_SOLVE` (Brown–Lowe joint gain): wins on the photometric
  fallback subset, one gate-fragility regression; disposition to be re-measured
  against the ToonOut-inclusive baseline.

Rejected with postmortems (do not re-attempt without new mechanism): GraphCut
seams (twice — fragmentation on flat cels is architectural), phase-aware
selection tie-break penalty, background mean/median averaging (block-overlay
banding), dense band-scan gate, Hugin as universal comparator (projection
singularity ≥~15-20 frames), AnimationSeparator as phase detector (built for
cyclic loops, fragments monotonic scrolls).

### Where quality actually stands

Failure taxonomy (from the critical evaluation's visual audit + Phase 4 triage):
- **Catastrophic upstream family** (matching/BA mistakes character motion for
  camera pan → misordered collage): now largely *guarded* into SCANS fallbacks
  rather than shipped, which is why "simple_better" counts dropped — safety,
  not quality.
- **Pose-gap family** (frames 300–800ms apart, 10–85px pose gaps the midpoint
  warp can only halve): the architectural wall. Frame selection is the named
  bottleneck since June; the DINOv2 flag is the current best lever.
- **Photometric family** (banding/exposure): the Phase 4 full-97 triage
  reframed the fallback population — only 1/27 seam_vis_gate fallbacks is
  clearly pose-blend-driven; 10/27 clearly photometric; 14/27 are within 10
  points of the gate limit. **A modest targeted photometric fix could flip a
  meaningful fraction of the 54 fallbacks.** This is the cheapest identified
  quality lever, and `.agent/cache/asp_seam_photometric_diagnosis_2026-08-07`
  indicates the per-test visual diagnosis has started.

## 5. Evaluation Infrastructure

- `just asp-benchmark` (full 97, ~2.5h on RTX 3090 Ti) / `asp-benchmark-verify`
  (5-test subset) / `asp-benchmark-assess` (PySide6 N-way inspector with
  zoom/pan-locked panels, comparison maps, keyboard-first 0-4 scoring,
  defect taxonomy, region annotation) / `asp-triage` (FiftyOne + MongoDB).
- Metrics: 12 validated (post-trim from ~40); ghosting measured by FFT
  autocorrelation (`ghosting_siqe`) after the infamous sharpness-proxy
  mislabeling; aligned-SSIM computed on real-content overlap only (§0.4b);
  SI-FID added for non-GT tests (2026-08-07); mean seam post-warp-diff as a
  pose-residual signal; one-directional human-coherence veto wired into
  verdicts.
- Known harness limits: benchmark re-implements parts of the pipeline by hand
  (issue #10's class of measurement bug — masking flags were unmeasurable until
  fixed; an audit of other flags is still open); host-freeze fixed via thread
  caps (confirmed at corpus scale); CI cannot run the real pipeline (GPU), and
  `backend` tests still collide with Image-Toolkit namespaces standalone (#3).

## 6. GUI & Product Surface

- `HybridStitchPanel` — the artist-facing manual tool: sequence sidebar,
  Control Points, Color Correct, Seam Painter, Mesh Warp, Render. Roadmap §0
  names it "the closest thing to shippable, artist-facing value." Now has: a
  first-run onboarding wizard tied to live tab switching (10 tests), a "Try a
  Sample" menu with three procedurally-generated bundled sequences (12 tests),
  and two docs-site tutorials.
- Stitch tab — front-end to the automated pipeline, composed of 11 sub-tab
  mixins.
- Recent GUI bug fixes: showEvent-based wizard trigger, superseded-wizard
  false-"seen" fix, q_app fixture repair (33/50 tests were failing at setup).
- Deleted by §0 decision: QML duplicate tab tree, Android/iOS scaffolds.
  Frozen: Tauri frontend.

## 7. Documentation

Strong: ARCHITECTURE.md (honest about partiality), TESTING/DEVELOPMENT/
TROUBLESHOOTING/GLOSSARY, 2 ADRs, research corpus (`Image_Stitching_Research.md`
consolidated field reference + comprehensive report), tutorials, state-of-the-
pipeline cache doc, postmortems for every failure.

Weak: README (stale template text — worst doc in the repo by a wide margin),
five doc toolchains for one project (flagged, unconsolidated), ROADMAP.md at
1,237 lines versus its own ≤~350-line budget (Ground Rule #3) — it has become
a session log; the CHANGELOG exists precisely to absorb that material.

## 8. Strengths to Keep (with reasons)

1. **The benchmark corpus + harness + comparators.** Irreplaceable; the only
   anime-stitching benchmark of its kind. Every good decision of the last month
   traces to it.
2. **The ground rules and postmortem culture.** The project's immune system
   against its own documented pathology (the 104-gate degenerate loop era).
3. **The trimmed 13-stage core + 8-gate budget.** Small enough to reason about;
   the "never average conflicting poses" principle is correct and now
   structurally embedded (A6, phase-composite).
4. **The C++ `base/` kernels behind pybind11.** Competent, recently exercised;
   the right performance architecture for this app (see §9 on rewrites).
5. **PySide6 as the sole GUI, HybridStitchPanel as product spine.** One UI
   paradigm, working today, correctly prioritized by §0.
6. **The research corpus + §R distillation.** Prevents re-surveying; encodes
   settled negative results (do-not-adopt list).
7. **Onboarding/tutorial work (Phase 6.1–6.3).** Directly serves the stated
   product vision; cheap, shipped, tested.
8. **The measured-flag discipline** — every OFF flag has numbers attached, and
   honest "mixed, needs eyes" verdicts instead of premature flips.

## 9. Weaknesses to Change (with reasons and avenues)

1. **README/identity debt.** The front door misdescribes the product.
   *Avenue*: rewrite around the ARCHITECTURE.md overview + product framing;
   trim badge wall to the real stack (Python, C++, TS-frozen); an hour of work.
2. **Template/polyglot overhead.** Gradle/Maven/Kotlin/Java/Go remnants, five
   doc toolchains, template ADR. *Avenues*: (a) minimal — delete unused
   language scaffolds + consolidate docs to MkDocs+Sphinx; (b) also add an ADR
   recording the consolidation decision.
3. **Roadmap-as-changelog.** 1,237 lines; violates its own budget; new sessions
   must wade through session archaeology to find the plan. *Avenue*: move all
   dated result blocks into `docs/moon/CHANGELOG.md` (its stated role) or
   `.agent/cache/`, leaving a ≤350-line plan: objective, ground rules, §R,
   per-phase current-state one-liners + next actions.
4. **Package identity / issue #3.** `backend`/`gui` top-level names collide
   with the host repo; imports mix `asp_backend.*` and `backend.src.*`.
   *Avenues*: (a) full rename to `asp_backend`/`asp_gui` with a compat shim for
   Image-Toolkit; (b) src-layout repackaging (`anime_stitch_pipeline.backend`);
   either unblocks standalone CI and honest `uv sync` environments.
5. **The Phase-0.1 bottleneck.** A ~45-min human rating pass gates every
   quality decision and has been open for a month while its tooling was
   polished. *Avenues*: (a) just schedule and run it (the correct first move);
   (b) additionally calibrate a VLM coherence judge (structured
   "duplicated/torn/misordered anatomy?" prompts) against the human ratings so
   future passes scale — with the explicit caveat that the S143 Qwen2-VL scorer
   was built and never used; a judge is only worth keeping if it demonstrably
   ranks like the human on the rated set.
6. **Pipeline state architecture.** Mixins over implicit `self` state require
   Protocol scaffolding to type-check and make stage boundaries untestable in
   isolation. *Avenues*: (a) explicit `PipelineContext` dataclass threaded
   through pure stage functions (the refactor `run_stage.py`'s docstring
   already names), enabling per-stage unit tests and checkpoint/resume;
   (b) leave as-is until after the quality plateau breaks — it is not the
   current bottleneck, just friction.
7. **No fast end-to-end regression test.** 911 unit tests pass while output
   quality is invisible to CI; the only e2e signal needs a 3090 Ti and 2.5h.
   *Avenue*: extend `data/samples/test_scroll_*` (synthetic scrolls with known
   GT) into a deterministic CPU-only 3-5 test micro-corpus run in CI with loose
   SSIM floors — catches "pipeline broke" (not "pipeline improved") cheaply.
8. **Distribution is unsolved for a desktop app.** No installer, no automated
   model-weight fetch (SAM-2 checkpoint was discovered missing mid-benchmark),
   CUDA-extra friction, AGPL+commercial dual license with no packaging story.
   *Avenues*: (a) PyInstaller/briefcase single-dir build + first-run weight
   downloader with checksums; (b) later, the frozen Tauri shell + Python
   sidecar; (c) explicit "minimum viable machine" doc (CPU-only path exists —
   the matching cascade degrades gracefully — but is unmeasured as a product
   config).
9. **On rewriting in C++/Rust (asked explicitly):** not recommended, and the
   evidence is in-repo. The hot paths are already C++; per-test time is
   dominated by ML inference (GPU) and algorithmic choices, not Python
   overhead; and the project's scarce resource is iteration speed on an
   unsolved research problem, which a compiled rewrite would throttle. The
   defensible endgame *if* the product ships broadly is ONNX-exported models +
   the existing C++ kernels behind a thin native shell — but that is a
   post-product-market-fit packaging decision, not a quality lever today.
10. **RL/optimization ambitions vs. settled history.** The stated purpose
    promises RL/swarm/evolutionary assistance; the S200 trim deleted exactly
    those subsystems as unverified. Phase 5.1's bounded reintroduction
    (RL-for-frame-selection first, PSO over gate thresholds second) is the
    right shape, but the tension should be resolved deliberately — either the
    product statement softens ("ML-assisted") or the roadmap elevates a
    bounded RL experiment once ratings exist to train against.

## 10. Risks

- **Motivation/allocation risk**: infra polishing (mypy, lint, harness) is
  legible and safe; the two moves that actually change the game (human rating
  pass; photometric-defect diagnosis on the borderline fallbacks) are less
  legible and keep slipping. The 2026-08-07 corpus run proving "nothing
  changed behavior" is the pattern in miniature.
- **Single-human dependency**: all quality ground truth flows through one
  person's eyes; no second rater, no inter-rater check planned.
- **Cross-repo entanglement**: ASP's tests/CI depend on Image-Toolkit's
  interpreter and conftest; the standalone story regresses silently.
- **Corpus privacy/licensing**: the benchmark corpus (R18/OVA captures) cannot
  ship, so external contributors can't reproduce quality claims; the synthetic
  sample generator is the seed of a shareable proxy corpus.

## 11. Bottom Line

Keep: the corpus, the harness, the ground rules, the trimmed core, the C++
kernels, PySide6 + HybridStitchPanel, the research base, the postmortems.

Change: run the human rating pass (everything is parked behind it); chase the
photometric fallback class (cheapest measured quality lever); fix the README
and package identity; trim the roadmap back to a plan; consolidate docs; decide
the north star (autonomous benchmark supremacy vs. assistive artist tool) and
let the exit-gate structure follow from that decision rather than precede it.
