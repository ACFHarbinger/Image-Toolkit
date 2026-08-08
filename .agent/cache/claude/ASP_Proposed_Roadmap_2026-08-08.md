# ASP Proposed Roadmap — Claude (Fable 5), 2026-08-08

*Input to the joint roadmap-writing session. Based on the full module analysis
(`.agent/reports/claude/ASP_Status_Report_2026-08-08.md`) plus the owner's
answers of 2026-08-08. This proposal is a replacement for
`submodules/ASP/docs/moon/ROADMAP.md`'s planning content (its dated result
blocks move to the CHANGELOG); it deliberately keeps the existing Ground Rules
verbatim — they are the project's immune system and none of the owner's answers
weakens them.*

---

## Identity & Release Gate (decided 2026-08-08)

**ASP is an assistive artist tool first**: a desktop app whose spine is the
interactive workflow (HybridStitchPanel + pipeline-intermediate editing), whose
automated pipeline is a proposal engine with far richer user-facing parameters
than alternatives, and whose target output is panoramic anime wallpapers.

**But the release bar is autonomous**: ASP is not "good enough to release"
until it matches or beats the OpenCV-class stitchers on **nearly all** of the
97 benchmark tests with *no human intervention beyond, at most, manual frame
selection* (the one concession made for cross-algorithm fairness). Human
judgment (soon VLM-assisted) remains the verdict authority.

Consequences of this pairing:
- The benchmark objective stays the release gate, but it no longer serially
  blocks product work — the assistive/product track and the quality track run
  in parallel by design (formalizing what §0 already half-decided).
- "At most manual frame selection" gives the benchmark a **new permitted
  configuration**: an ASP run fed human-curated (or later RL-curated) frame
  subsets. This should become an explicit benchmark mode
  (`--frames-from <selection.json>`), because it is both the fairness
  concession *and* the training interface for the RL frame-selection work.
- RL / mathematical optimization is elevated from "parked stretch" to a
  first-class track (it is close to being the point for the owner) — still
  bounded by the same one-change-one-benchmark discipline that governs
  everything else.

## Ground Rules — carried over unchanged

1. One change → one benchmark → keep or revert (5-test verify per change, full
   97 before default flips; record the JSON filename).
2. Human visual verdict outranks every metric. **Amended mechanism, per owner**:
   after the initial human pass, a calibrated VLM judge scores routine runs;
   the human re-checks any test whose score/verdict moves drastically
   (threshold to define in Phase A.3). The human remains the authority; the
   VLM is a scaling mechanism, never a replacement.
3. Budgets: ≤ ~50 env flags, ≤ 10 gates (new gate displaces an old one),
   roadmap ≤ ~350 lines; shipped items → CHANGELOG; failures → postmortems in
   `.agent/cache/`.
4. The human owns priorities and quality calls; agents implement and measure.
5. Anti-goals carry over: no unmeasured default-ON, no threshold-tuning
   sessions, no speculative default-OFF flags, no trusting `asp_better`
   without looking at the image.

---

## Phase A — Measurement Endgame *(first; unblocks everything)*

- **A.1 Human coherence rating pass** — owner-committed for the weekend of
  2026-08-08/09 (`just asp-benchmark-assess`, ~45 min, 97 tests, per-dimension
  sub-scores + defect tags). This is the single highest-leverage action in the
  project; everything below either consumes its output or is reordered by it.
- **A.2 Metric calibration** (existing item 0.2, now runnable): rank-correlate
  the 12 automated metrics against A.1 per-dimension; demote any metric that
  disagrees with the human ranking to diagnostic-only; keep the one-directional
  human-coherence veto.
- **A.3 VLM coherence judge**: prompt a vision LLM per test with the ASP/simple
  side-by-side (+GT where present) for a structured verdict (coherence 0–4;
  defect taxonomy: duplicated/torn/misordered anatomy, banding, ghosting;
  preference + confidence). Calibrate against A.1 (target: rank agreement on
  the rated set; report per-dimension correlation). Wire into the benchmark as
  the routine verdict source with a **drastic-change tripwire**: any test whose
  judge score moves ≥ N points (or verdict class flips) between runs is queued
  for human re-check. Lesson encoded: the S143 Qwen2-VL scorer died from never
  being routed into decisions — the judge ships *inside* the verdict path or
  not at all.
- **A.4 Flag dispositions** (the backlog A.1 unblocks): decide default-ON/OFF
  with full-97 + coherence evidence for `ASP_HOLD_AVERAGE`,
  `ASP_PHASE_COMPOSITE`, `ASP_POSE_WINDOW_PX=80`, `ASP_JOINT_GAIN_SOLVE`
  (re-measured against the ToonOut-inclusive baseline), `ASP_USE_SAM2`.
- **A.5 Benchmark manual-selection mode**: `--frames-from` per-test frame
  lists, reported as a separate configuration column (the fairness concession
  made concrete; doubles as the RL-selection evaluation interface for Track D).

*Exit gate*: ratings file exists; VLM judge calibrated + wired with tripwire;
every currently-measured flag has a decided disposition.

## Phase B — Close the Quality Gap *(the release-gate work)*

- **B.1 Photometric fallback conversion** (cheapest measured lever): finish the
  per-test visual diagnosis started 2026-08-07
  (`asp_seam_photometric_diagnosis_*`); fix the actual banding/exposure defect
  on the borderline tests (14/27 seam_vis_gate + 8/26 composite_gate_sb within
  ~10 points of their limits). Target: flip a meaningful fraction of the 54
  guarded fallbacks into true composites that pass A.3's coherence judgment.
- **B.2 Frame-selection pose gap** (the architectural wall): DINOv2
  pose-window selection (first-ever `asp_better` flip this session) iterated
  under the now-fixed measurement stack; then Track D.1's RL selection as its
  successor. Evaluate under both autonomous and A.5 manual-selection modes.
- **B.3 Per-flag interaction pass**: once individual dispositions exist (A.4),
  one full-97 run of the winning combination (flags are currently only measured
  in isolation).
- **B.4 VRAM profiles** (owner requirement — desktop dual-3090Ti vs laptop
  4080): a supported `ASP_PROFILE={high,low}` pair covering model choice
  (SAM-2 vs BiRefNet-only, RoMa on/off), batch sizes, and offload behavior;
  benchmark the low profile at least once at full-97 so its quality delta is
  known rather than assumed; document minimum-viable hardware.

*Exit gate (release bar)*: on the full corpus, ASP human/VLM-judged ≥ simple
stitch on nearly all tests (owner defines the tolerated exception count) in
autonomous or manual-frame-selection mode, with `asp_better` on
coverage/sharpness wherever a true composite ships.

## Phase C — Full 2D Canvas: Horizontal & Diagonal Scroll *(unparked; owner
has strong appetite — promoted from "parked until Phase-4 exit" to an active
track after A, parallel with B)*

Today non-vertical scroll gates to SCANS (stage 9.5); canvas/warp/seam code
assumes 1D vertical layout. This is the largest single engineering item in the
proposal (multi-week, high blast radius) — staged to keep every step
benchmarkable:

- **C.1 Axis-generalized geometry**: replace scroll-axis special-casing with a
  dominant-motion-vector formulation (translations already come from BA as 2D;
  the 1D assumption lives in canvas construction, midplane shift, seam
  orientation, content trim). Acceptance: vertical corpus results byte-stable
  (pure refactor, verified by full-97 before any behavior change).
- **C.2 Horizontal scroll support**: enable the generalized path for
  horizontal sequences; extend the DP seam cut to cut along the orthogonal
  axis. Needs new benchmark data — start with synthetic (rotate/transpose the
  existing generator), then a small real horizontal corpus (~10–15 tests with
  2–3 GTs) so the mode has its own measured baseline rather than inheriting
  vertical's.
- **C.3 Diagonal scroll**: arbitrary scroll direction = 2D canvas placement +
  seam finding that can no longer be 1D-DP-per-boundary. Candidate avenues,
  to be A/B'd, not decided here: (a) rotate-to-dominant-axis preprocessing
  (cheapest; reuses the whole 1D machinery; costs one resample); (b) true 2D
  seam via graph-cut *scoped only to this mode* (the flat-cel fragmentation
  postmortem was measured on the 1D-competitive path; 2D has no incumbent, so
  the do-not-revisit clause doesn't bind — but it must clear the same
  coherence judgment); (c) per-pixel phase-consistent reconstruction (the §9.2
  Stage-2 idea) which never needed seams to be 1D in the first place.
- **C.4 StabStitch++-style trajectory smoothing** (parked item that "pairs
  naturally"): only alongside C.2/C.3, never alone.
- **C.5 GUI**: HybridStitchPanel canvas/mesh/seam tools follow the axis
  generalization (they largely operate in 2D already; audit + fix
  assumptions).

## Phase D — RL & Mathematical Optimization Track *(elevated: an important
means, near-the-point; gated on Phase A's judge, NOT on Phase B's exit)*

The pre-trim RL/PSO/RLHF deletion remains settled evidence about *undisciplined
use*, not about the methods. Every item here is one bounded experiment with a
scheduled A/B, trained/evaluated against the A.1/A.3 coherence signal — the
optimization target that never existed pre-trim.

- **D.1 RL frame selection** (priority 1; the field's own "most important
  unimplemented idea"): policy proposes per-test frame subsets; evaluated via
  A.5's manual-selection benchmark mode; reward = VLM-judge coherence +
  coverage, human-audited via the tripwire. Must beat both the greedy default
  and DINOv2 selection (B.2) to earn default status. Start with the simplest
  formulation that can work (contextual bandit / small policy over candidate
  windows, offline evaluation on cached pipeline runs) before anything deep.
- **D.2 PSO/evolutionary search over gate thresholds + ARAP/warp parameters**
  (~8 gates + regularization weights): small legible search space, objective =
  judge score over the corpus; any found configuration ships only via the
  normal full-97 + disposition path.
- **D.3 Evolutionary photometric parameter search** (gain priors, feather
  curves): only if B.1 concludes the remaining photometric gap is parametric
  rather than architectural.
- **D.4 (stretch) Learned seam/compositing** (`stitch_net.py` exists): explicit
  proposal + owner sign-off required before any training run; the RLHF
  postmortem is mandatory pre-reading.

## Phase E — Product & Repo Hygiene *(parallel, low-risk, mostly one-offs)*

- **E.1 README rewrite** (the front door still says "template repository, ships
  no product code"): product pitch + real stack + usage; badge wall trimmed.
- **E.2 Package identity / issue #3**: rename top-level packages to
  `asp_backend` / `asp_gui` (finishing the split the code already half-made);
  Image-Toolkit side gets a thin compat shim. Integration bar per owner: at
  minimum a `Launch ASP App` button in Image-Toolkit — so the coupling can be
  process-level, not import-level. Unblocks standalone CI collection.
- **E.3 Docs consolidation** (owner-decided): **drop Structurizr and Doxygen**;
  keep MkDocs (portal) + Sphinx (API autodoc), with the **Vue site as the
  presentation layer that ingests MkDocs/Sphinx build output** — i.e. the Vue
  site renders, it does not maintain a parallel toolchain. One ADR records the
  decision; C4 content worth keeping becomes plain Mermaid/markdown in
  ARCHITECTURE.md.
- **E.4 Roadmap hygiene**: this replacement stays ≤ ~350 lines; all dated
  result blocks from the current 1,237-line roadmap move to
  `docs/moon/CHANGELOG.md` / `.agent/cache/` (Ground Rule #3 enforced on the
  roadmap itself).
- **E.5 Fast e2e micro-corpus in CI**: extend `data/samples/test_scroll_*`
  (synthetic, CPU-only, deterministic) to 3–5 sequences incl. one horizontal +
  one diagonal (feeds C); loose SSIM floors; catches "pipeline broke", not
  "pipeline improved".
- **E.6 Model-weight bootstrap**: one `just asp-fetch-weights` recipe
  (checksummed downloads for ToonOut/BiRefNet, SAM-2 checkpoint, DINOv2, …) —
  the SAM-2 checkpoint was discovered missing mid-benchmark; first-run UX and
  reproducibility both need this.
- **E.7 Light packaging** (personal-use scale, not commercial): PyInstaller or
  Briefcase single-dir build for desktop + laptop; full installer work stays
  out of scope until after the Phase-B release bar.

## Explicitly Dropped / Kept-Parked

- **Dropped**: Structurizr + Doxygen toolchains (E.3); the "beat OpenCV before
  any product work" serialization (replaced by parallel tracks + release bar);
  mobile scaffolds (already deleted); QML (already deleted).
- **Kept parked**: Tauri frontend (frozen until after the Phase-B release bar;
  revisit as the packaging shell in E.7's successor); full commercial
  distribution; generative fill/SR enhancers (old Phase 5 list — each still
  needs the LPIPS/CLIP gate and a measured A/B, now also the VLM judge);
  ASP→HybridStitch automated handoff polish until quality no longer needs the
  harness to validate every change.

## Sequencing Summary

```
Weekend:  A.1 human rating pass (owner)
Then:     A.2–A.5 (agents)  ──┬── B.1 photometric → B.2 selection → B.3/B.4
                              ├── C.1 refactor → C.2 horizontal → C.3 diagonal
                              ├── D.1 RL selection → D.2 PSO gates (needs A.3)
                              └── E.* hygiene items (anytime, low risk)
Release bar: Phase B exit gate, judged by A.3's calibrated judge + human audit.
```

The critical path is A.1 → A.3: every track (flag flips, photometric
conversion, RL reward, 2D-mode acceptance) consumes the coherence signal. The
project has been one 45-minute human session away from unblocking itself for a
month — that observation, more than any architecture idea, is this proposal's
core claim.
