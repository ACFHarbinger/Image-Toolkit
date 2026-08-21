# Anime Stitch Pipeline (ASP) — Comprehensive Analysis Report

**Author:** Grok (xAI coding assistant)  
**Date:** 2026-08-08  
**Scope:** Code, documentation, research, roadmaps, benchmarks, packaging, and product posture of `submodules/ASP` (Anime-Stitch-Pipeline), analysed first as a **standalone desktop application**, second as an Image-Toolkit submodule.  
**Sources:** `README.md`, `docs/ARCHITECTURE.md`, `docs/moon/ROADMAP.md`, `docs/moon/CHANGELOG.md`, `docs/reports/ASP_Critical_Evaluation_2026-07-08.md`, `docs/research/*`, `.agent/cache/asp_state_of_the_pipeline.md`, tutorials, ADRs, CMake/pyproject packaging, and a structural read of `base/`, `backend/`, `gui/`, `frontend/`, and benchmark tooling.  
**Status:** Independent technical assessment for product/architecture brainstorming. Not a benchmark re-run; quality numbers cited from project checkpoints through 2026-08-07.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Mission vs Reality](#2-mission-vs-reality)
3. [Repository Map](#3-repository-map)
4. [Architecture](#4-architecture)
5. [The Automated Pipeline](#5-the-automated-pipeline)
6. [HybridStitch — The Manual Studio](#6-hybridstitch--the-manual-studio)
7. [C++ Core (`base/`)](#7-c-core-base)
8. [Benchmark, Evaluation & Measurement Culture](#8-benchmark-evaluation--measurement-culture)
9. [Quality State (Corpus Checkpoints)](#9-quality-state-corpus-checkpoints)
10. [Research Base & Established Decisions](#10-research-base--established-decisions)
11. [Roadmap Landscape](#11-roadmap-landscape)
12. [Packaging, Coupling & Standalone Readiness](#12-packaging-coupling--standalone-readiness)
13. [GUI, Frontend & Meta-Infrastructure](#13-gui-frontend--meta-infrastructure)
14. [Tutorials & Onboarding](#14-tutorials--onboarding)
15. [ML, Optimisation & Deferred Ambitions](#15-ml-optimisation--deferred-ambitions)
16. [Pros — What to Keep (and Why)](#16-pros--what-to-keep-and-why)
17. [Cons — What Hurts (and Why)](#17-cons--what-hurts-and-why)
18. [What to Change — Options Matrix](#18-what-to-change--options-matrix)
19. [What Not to Do](#19-what-not-to-do)
20. [Recommended Priority Stack](#20-recommended-priority-stack)
21. [Open Questions for Stakeholders](#21-open-questions-for-stakeholders)
22. [Appendix A — Approximate Size Inventory](#22-appendix-a--approximate-size-inventory)
23. [Appendix B — Gate Set (Complete)](#23-appendix-b--gate-set-complete)
24. [Appendix C — Notable Env Flags](#24-appendix-c--notable-env-flags)
25. [Appendix D — Key File Index](#25-appendix-d--key-file-index)

---

## 1. Executive Summary

The Anime Stitch Pipeline (ASP) is a desktop-oriented system for turning ordered sequences of scrolling anime/manga (or similar cel-shaded) capture frames into a single panoramic image. It has **two independent stitching paths**:

| Path | Entry | Nature |
| --- | --- | --- |
| Automated | `AnimeStitchPipeline` (Stitch tab / CLI-ish pipeline run) | 13-stage ML + classical CV cascade with quality gates and SCANS fallback |
| Manual / HITL | `HybridStitchPanel` | Human-directed control points, colour, seams, mesh warp, render |

**Honest verdict in one paragraph:**  
ASP is a **serious research stitcher with unusually good measurement discipline and research documentation**, sitting next to a **genuinely usable manual studio (HybridStitch)**, trapped in **incomplete standalone packaging** (deep Image-Toolkit coupling + leftover template scaffolding), and **blocked on the one human measurement its own ground rules require** (Phase 0.1 coherence ratings: tool rebuilt, rating pass still open). The pre-trim failure mode—adding hundreds of unmeasured flags/gates and optimising metrics blind to structural coherence—was correctly diagnosed (July 2026 critical evaluation) and culturally corrected by the S200 “great trim.” The remaining gap is **product focus + upstream frame/phase selection + finishing human ratings**, not another compositing micro-feature.

**Mission fit:** The stated purpose (desktop app, anime cel focus, ML + mathematical optimisation assistance, tutorials for beginners) is coherent. Execution today is strongest on **classical CV + guarded automation + HybridStitch + tutorials scaffolding**, and weakest on **shipped default-on ML assistance** and **auto quality parity with OpenCV SCANS on human coherence**.

**As a standalone app:** not fully releasable without packaging work.  
**As a submodule:** load-bearing for Image-Toolkit’s animation path, but parent/child dependency direction is inverted in places (ASP imports parent constants/errors; C++ cannot build without parent headers).

---

## 2. Mission vs Reality

### 2.1 Stated purpose (from product intent)

A desktop application that lets users:

1. Edit images and stitch them into a panoramic result  
2. Focus on **anime-style cel-shaded art** (flat fills, line art, animation pose change under camera pan)  
3. Leverage **ML** (deep learning, RL, etc.) and **mathematical optimisation** (swarm, evolutionary, etc.) to reduce artist labour  
4. Include **tutorials** so beginners can learn editing and the tool itself  

### 2.2 What actually ships today

| Intent | Reality |
| --- | --- |
| Desktop app | **Yes** — PySide6 `gui/` is the working surface |
| Panorama stitch for scroll captures | **Yes** — auto + Hybrid paths |
| Anime / cel domain specialisation | **Yes** — domain model, matchers, fg/bg split, pose handling are anime-aware |
| ML assistance default-on | **Partial** — BiRefNet/ToonOut, LoFTR family, optional SAM-2/RoMa/SEA-RAFT; many high-ambition systems deleted or flag-OFF |
| RL / swarm / evolutionary assist | **Not in default path** — pre-trim implementations deleted; Phase 5.1 documents narrow reintroduction only after quality gates |
| Tutorials / onboarding | **Partial / recent** — Hybrid onboarding wizard, docs tutorials, sample sequences; assisted suggestions emerging |
| Beat or match OpenCV simple stitch on human quality | **Not yet** — ~56% guarded fallbacks on full corpus; true composites still trail on coherence-critical cases |
| Standalone installable product | **No** — submodule/template residue, dual namespaces, C++ tied to Image-Toolkit |

### 2.3 The domain problem (correctly framed)

Classical panorama stitchers assume adjacent frames differ mainly by camera motion. Anime pan shots violate that:

\[
F_{\text{fg}} = T_{\text{camera}} + A_{\text{animation}}(x,y)
\]

When \(A_{\text{animation}}\) is large (pose change between selected frames), blending two frames produces ghosting, torn anatomy, or duplicated limbs. ASP’s correct architectural response:

1. Align **background** rigidly (translation / limited affine — not full homography on flat cels).  
2. Measure **foreground residual** (flow / registration).  
3. Warp toward agreement (midpoint + ARAP), or **escalate to a single coherent pose** when the gap is too large.  
4. **Never average two conflicting poses** as the default recovery.

This framing matches the research base and is a genuine strength. Failure is mostly in **execution upstream of compositing** (selection/matching/BA placing frames wrong) and in **measurement** (metrics that cannot see structural incoherence).

---

## 3. Repository Map

Location in Image-Toolkit: `submodules/ASP/` (git submodule; historically also known as Anime-Stitch-Pipeline).

```
ASP/
├── base/                 C++ kernels (matching, BA, canvas, seam, compositing, …)
├── backend/              Python pipeline, models, benchmark, validation
│   ├── src/              Core package (orchestration, alignment, rendering, …)
│   ├── benchmark/        Full corpus harness, Overmix/Hugin runners, evaluation UI
│   ├── config/           default.yaml / asp_config.toml-style config
│   ├── test/             pytest suite (~900+ tests when environment is correct)
│   └── validation/       Static analysis / dependency graph tooling
├── gui/                  PySide6 desktop UI (Stitch tab + HybridStitch)
├── frontend/             Tauri scaffold — frozen
├── docs/                 Architecture, research, moon roadmap, tutorials, ADR, site
├── data/samples/         Sample PNG sequences
├── env/                  conda/pip env definitions
├── tools/                justfile submodules (bench, build, test, docs, …)
├── .agent/               Agent rules, cache postmortems, prompts
├── justfile              Root task runner
└── pyproject.toml        uv workspace root (members: backend, gui)
```

**Not product code (or frozen):**

- `frontend/` — Tauri placeholder, frozen until Phase-4 quality gate  
- Mobile scaffolds — **deleted** (2026-08-06 product-scope pass)  
- `gui/qml/` — **deleted** (duplicate UI paradigm)  
- Much of `docs/website/` history / multi-toolchain residue — consolidation partially done  

**Documentation identity split:** Top-level `README.md` still mixes product tagline with **GitHub template** boilerplate (“ships no product code of its own”). `docs/ARCHITECTURE.md` and tutorials are closer to truth. `.agent/AGENTS.md` still has template TODOs. This is a documentation debt that confuses both humans and agents.

---

## 4. Architecture

### 4.1 Module boundaries (as documented and observed)

| Module | Language | Responsibility |
| --- | --- | --- |
| `base/` | C++17 | Performance-critical kernels; exposed via **Image-Toolkit’s** `base` pybind11 module (not a fully independent extension today) |
| `backend/` | Python 3.11+ | Orchestration (`AnimeStitchPipeline`), ingestion, matchers, models, rendering, HITL session, benchmarks |
| `gui/` | Python / PySide6 | Desktop UI: automated Stitch tab + HybridStitch + HITL dialogs |
| `frontend/` | TS / Rust (Tauri) | Scaffold only, frozen |
| `docs/` | Markdown + MkDocs/Sphinx | Product/docs/API surface |

### 4.2 Intended data flow (automated path)

```
Frames (paths / video decode)
    → smart selection + hold detection + optional phase detect
    → load / sort / width-normalise
    → photometric prep (BaSiC, vignetting, bg scalar norm)
    → fg/bg masks (BiRefNet / ToonOut; optional SAM-2)
    → matching cascade → edge graph filters / dedup
    → GNC-TLS bundle adjustment → affine validation / retries
    → scroll-axis / dy_cv / connectivity gates → SCANS if unsafe
    → flow / ECC refine
    → canvas construction
    → A5 fg-excluded temporal median (bg plate)
    → Stage 11 fg composite (register → gain → DP seam → Laplacian blend)
    → content trim / fill / crop / save
```

### 4.3 Dual-path product architecture

```
                    ┌─────────────────────┐
   User frames ────►│  HybridStitchPanel  │──► manual panorama
                    │  (artist control)   │
                    └──────────┬──────────┘
                               │ sequence handoff (partial)
                    ┌──────────▼──────────┐
   User frames ────►│ AnimeStitchPipeline │──► auto panorama
                    │  (+ quality gates)  │      or SCANS fallback
                    └─────────────────────┘
```

**Critical product gap:** ASP → HybridStitch handoff (import auto affines, seams, masks, phase labels into editable tools) is **parked** on the roadmap. Without it, the two paths are co-located apps rather than one assisted workflow.

### 4.4 Design patterns in code

- **Mixin composition** for `AnimeStitchPipeline` (`_RunStageMixin`, `_MatcherSelectionMixin`, `_FilterEdgesMixin`, `_ThinWrappersMixin`) + `TYPE_CHECKING`-only `_PipelineHost` Protocol for mypy.  
- **Graceful optional imports** via `_probes.py` (`_LOFTR_OK`, `_ROMA_OK`, `_SEA_RAFT_OK`, …).  
- **C++ fast path with Python fallback** pattern (`_native.py` probes under rendering/compositing/frame_selection/…).  
- **Env-var configuration** loaded optionally from TOML (`core/config.py` → `os.environ.setdefault`).  
- **HITL session serialisation** (JSON with ndarray base64 encoding, size-capped).  

These are competent engineering choices for a research+product hybrid. The main structural cost is **opacity of the default path** (flags + mixins + dual package names).

---

## 5. The Automated Pipeline

### 5.1 Stage table (default-on conceptual path)

Derived from `.agent/cache/asp_state_of_the_pipeline.md` (post-trim state) and `run_stage.py`:

| Stage | Role | Primary location |
| --- | --- | --- |
| 0 | Smart frame selection (displacement, holds, blur/contrast reject) | `ingestion/frame_selection/` |
| 1–2 | Load, numeric sort, width normalise | `alignment/canvas.py` |
| 3 | BaSiC flat-field (when enabled) | `rendering/photometric.py` |
| 4 | BiRefNet / ToonOut fg masks; optional SAM-2 | `ingestion/masking.py` |
| 4.5 | Background photometric normalisation | pipeline photometric stage |
| 5–6 | Matcher cascade + static-edge / spread / bg-ratio filters | `alignment/matching/` |
| 6.5 | Spatial dedup, connectivity gate, high-conf retry | pipeline |
| 7 | GNC-TLS bundle adjustment | `alignment/bundle_adjust.py` + C++ |
| 7b | Affine validation + PANORAMA → SCANS retry chain | `core/validation.py` |
| 7c | dy_cv gate (irregular scroll → SCANS) | pipeline |
| 8 | SEA-RAFT / ECC refine | `flow/`, `alignment/ecc.py` |
| 9 | Canvas + midplane; horizontal scroll special-case | `alignment/canvas.py` |
| 10 | A5 fg-excluded temporal median | `rendering/rendering/` |
| 10.5 | Multi-frame coverage gate | pipeline |
| 8.5 / 11 | Fg registration + composite (seams, gain, Laplacian) | `rendering/compositing/` |
| 12.5–13 | Content trim, TELEA fill, crop, save | pipeline / canvas |

### 5.2 Stage 11 composite (order of operations)

1. Warp frames + masks to canvas  
2. Bg-scalar normalisation  
3. Boundary optimisation (±SEARCH_RANGE, bg-weighted similarity)  
4. Fg registration per seam: flow → ARAP Push+Regularise → midpoint warp → single-pose escalation  
5. Feather adaptation by post-warp residual  
6. Sequential global gain (joint gain solve is flag-gated, default OFF)  
7. Pairwise DP seams + Laplacian multi-band blend (GraphCut path exists, default OFF)  
8. Black-pixel fill + seam audits into metadata  

**Master principle (research + practice):** never average two conflicting poses — warp to agreement or pick one; a skipped frame beats a torn average.

### 5.3 Matcher cascade

Typical order (with graceful degradation):

1. EfficientLoFTR  
2. kornia LoFTR  
3. ALIKED + LightGlue  
4. Template match  
5. Phase correlation  
6. RoMa (optional / extra)  

Heavy research deps (`sam-2`, `ptlflow`, `romatch`, `mamba_ssm`) live in optional `matchers` extra so `uv sync` works without a CUDA toolchain — a real fix (issue #5 era).

### 5.4 Safety philosophy

ASP prefers **guarded fallback to SCANS** (`cv2.Stitcher`-style simple stitch on preprocessed frames) over shipping a known-bad composite. Gates include connectivity, affine validation, dy_cv, coverage, and benchmark-side composite/ghost/seam-visibility gates.  

**Implication for product UX:** “auto” often means “expensive attempt then safe OpenCV.” That is scientifically honest and artist-protective, but it must be communicated so users do not interpret SCANS output as “the ML result.”

### 5.5 Known algorithmic ceiling

Documented repeatedly since early June 2026:

- Frames selected hundreds of ms apart create **pose gaps of tens of pixels**.  
- Midpoint warp halves gaps; it does not close large animation deltas.  
- When matching treats character motion as camera pan, BA places strips wrong; the temporal median becomes an incoherent collage **before** any seam can help.  
- Therefore: **selection + phase consistency dominate**; compositing polish has diminishing returns on the catastrophic failure family.

Rejected or mixed experiments (postmortems in `.agent/cache/`):

| Experiment | Outcome |
| --- | --- |
| `ASP_PHASE_AWARE_SELECT` | Rejected — no post_warp_diff win; one real regression |
| `ASP_BG_AVERAGE` | Rejected — banding from misaligned overlay content |
| GraphCut seams | Rejected twice — fragmentation on flat cels |
| Dense band-scan gate | Rejected — no measured effect |
| `ASP_JOINT_GAIN_SOLVE` | Mixed — real wins + residual banding; stays OFF pending human ratings |
| `ASP_HOLD_AVERAGE` / `ASP_PHASE_COMPOSITE` | Measured positive-ish; stay OFF pending human pass |
| `ASP_USE_SAM2` | Runnable after bugfixes; quality mixed; default OFF |
| `ASP_POSE_WINDOW_PX` (DINOv2) | First real `asp_better` flip in an Aug session; mixed; needs eyes |

---

## 6. HybridStitch — The Manual Studio

### 6.1 What it is

`gui/src/tabs/stencil/hybrid_stitch_panel.py` — `RealHybridStitchPanel`:

- Left: ordered frame sequence with thumbnails  
- Right: tool tabs — Control Points, Color Correct, Seam Painter, Mesh Warp, Render  
- Supporting widgets under `gui/src/tabs/widgets/`  
- Workers under `gui/src/helpers/` for off-main-thread work  

### 6.2 Product significance

The 2026-08-06 whole-app review correctly identified HybridStitch as **the closest shippable artist-facing value** independent of whether the automated pipeline ever beats OpenCV. That assessment still holds.

HybridStitch is where the mission’s “edit images + stitch” actually lives as a **user-controlled craft tool**. Automation can assist it later; it should not be treated as a second-class fallback UI.

### 6.3 Onboarding (recently shipped)

- `HybridStitchOnboardingWizard` — first-run, non-modal, re-invocable via “?”  
- Bundled synthetic sample sequences (“Try a Sample”) — SFW procedural art (corpus explicit-content constraint respected)  
- Docs: `docs/tutorials/getting-started-hybridstitch.md`, `pipeline-overview.md`  

### 6.4 Gaps relative to vision

- Auto → Hybrid **state handoff** incomplete (affines/seams/masks/phases not fully imported as editable starting points)  
- Assisted suggestions (stats recommendations / seam diagnostics) exist in pieces; trustworthiness still tied to auto pipeline quality  
- Not yet a full “studio” narrative (project files, undo stacks across tools, export presets, multi-phase projects)

---

## 7. C++ Core (`base/`)

### 7.1 Sources

| File | Role (approx.) |
| --- | --- |
| `matching.cpp` | Matching hot paths |
| `bundle_adjust.cpp` | GNC-TLS / robust BA pieces |
| `validation.cpp` | Affine validation |
| `canvas.cpp` | Canvas construction |
| `seam.cpp` | Seam cut / GraphCut hooks |
| `compositing.cpp` | Laplacian blend / composite kernels |
| `exposure.cpp` | Photometric / gain helpers |
| `frame_selection.cpp` | Selection-related acceleration |
| `fg_register.cpp` | ARAP / fg registration |

Roughly **~4.2k LOC** C++ after trim — small, focused, appropriate.

### 7.2 Build reality (critical)

`base/CMakeLists.txt` states explicitly:

- This C++ core **does not build a standalone Python extension**.  
- Sources are compiled into **Image-Toolkit’s single `base` pybind11 module**.  
- Shared headers (`affine_types.hpp`, `common.hpp`, …) come from **Image-Toolkit `base/include/`**, not vendored in ASP.  
- Local CMake exists so Catch2 tests can run in isolation **assuming** the submodule is checked out inside Image-Toolkit.

**Standalone implication:** ASP cannot be built or shipped as a pure independent binary stack without a deliberate native-module extraction (recommended long-term: `asp_native` owning these sources).

### 7.3 Recommendation on rewrite

- **Keep C++ for kernels** — correct performance cut.  
- **Do not full-rewrite the orchestrator to C++/Rust** expecting quality miracles; coherence is not a language problem.  
- **Expand C++** only where profiling shows Python orchestration or per-pixel loops dominate (often models/matching dominate wall time, not DP seam alone).  
- A **full C++ Qt app rewrite** would discard PySide + Torch velocity with little quality upside; only justify after product-market fit and proven performance walls.

---

## 8. Benchmark, Evaluation & Measurement Culture

### 8.1 Assets

- **97-test corpus**, **55 with ground truth** — unique strategic asset  
- `backend/benchmark/bench_anime_stitch.py` — primary harness  
- Comparators: OpenCV SCANS (simple), **Overmix** (external GPL tool), **Hugin** (partial coverage on long planar scrolls)  
- Human rating / inspector: `backend/benchmark/evaluation/` + `eval_dispatch.py`  
- FiftyOne triage surface (optional `benchmark-eval` extra)  
- Diagnostics: seam photometrics, fallback class triage, resource/thread caps  

### 8.2 Ground rules (non-negotiable culture)

1. **One change → one benchmark → keep or revert** (5-test verify; full 97 before default flips).  
2. **Human visual verdict outranks every metric.**  
3. Budgets: ≤ ~50 env flags, ≤ ~10 gates, roadmap ≤ ~350 lines (see §11 — currently violated on flags and roadmap size).  
4. Human owns priorities; agents implement and measure.  

These rules are the project’s best defence against pre-trim failure modes.

### 8.3 Metric caveats (load-bearing history)

From the critical evaluation and state docs:

- Laplacian sharpness can **reward torn seams**.  
- Early “ghosting” metrics were sharpness proxies.  
- GT-SSIM rewards coverage/tone and can **score incoherent collages above coherent simple stitches** (documented metric inversions: e.g. test84, test53 family).  
- **No automated metric currently measures structural coherence** (“does this parse as one character in one picture”).  

Hence: side-by-side montages and human scores are mandatory for “done.”

### 8.4 The open measurement blocker

**Phase 0.1 human coherence ratings:** inspector/tooling rebuilt; **the actual rating pass is still open**.  

Until that file of human judgments exists:

- Default-ON flips for measured-positive flags remain correctly blocked.  
- Metric calibration (Phase 0.2) cannot run.  
- RL / evolutionary search against “quality” has no trustworthy reward.

This is not a code gap; it is a **human process gap** with outsized leverage.

### 8.5 Benchmark harness lessons

- Host freezes were real (uncapped OpenMP/BLAS/OpenCV/Torch threads); **thread cap fix confirmed at full-corpus scale**.  
- Historical bug: benchmark sometimes **reimplemented pipeline stages** instead of calling `AnimeStitchPipeline` (e.g. SAM-2 A/B measurement hole, issue #10) — treat harness fidelity as a first-class correctness concern.  
- Full 97-run cost is ~2–3 hours on a high-end GPU machine; infrastructure must stay green or research velocity collapses.

---

## 9. Quality State (Corpus Checkpoints)

Numbers below are **project-recorded**, not re-measured in this analysis.

| Checkpoint | asp_better / comparable / simple_better | Notes |
| --- | --- | --- |
| 2026-07-09 post-trim baseline | 27 / 41 / 29 | Aligned GT-SSIM ~0.693 vs 0.718; 51 composites / 46 fallbacks |
| 2026-07-28 full corpus | 21 / 54 / 22 | 43 composites / 54 fallbacks; ToonOut + gate honesty; sharpness/ghosting ASP-strong |
| 2026-08-07 full corpus | ~22 / 53 / 22 | Statistically same as 07-28 after infra/bugfix session; **composite quality gap unchanged** |

**Fallback class picture (full corpus, late July):**

- `seam_vis_gate` ~27  
- `composite_gate_sb` ~26  
- other classes negligible  

Re-analysis: many `seam_vis_gate` cases are **photometric** (low post_warp_diff, high seam visibility), not pure pose tears — so Phase 4 is “fix photometrics on borderline tests,” not only “fix pose blend.”

**Architecturally ASP-strong dimensions (when composites ship):**

- Coverage / framing (less crop than naive OpenCV on some tests)  
- Sharpness (sub-pixel alignment)  
- True periodic ghosting (SIQE-style)  

**Architecturally SCANS-strong dimension:**

- Coherence by construction (adjacent frames ⇒ tiny \(A_{\text{animation}}\))  

---

## 10. Research Base & Established Decisions

### 10.1 Documents

- `docs/research/Image_Stitching_Research.md` — consolidated field reference  
- `docs/research/ASP_Comprehensive_Research_Report.md` — algorithm specs, datasets, architecture  
- `docs/reports/ASP_Critical_Evaluation_2026-07-08.md` — independent post-mortem of ~200 sessions  
- Field notes: Overmix, Hugin  
- Postmortems: GraphCut, bg average, phase-aware select, joint gain, ToonOut, etc.  

### 10.2 Established and still valid

- Translation / limited affine geometry (homography/APAP ill-conditioned on flat cels)  
- Matcher recipe (EfficientLoFTR → … → RoMa)  
- GNC-TLS BA  
- BiRefNet / ToonOut masking  
- A5 fg-excluded median  
- ARAP + midpoint warp + single-pose escalation  
- Multi-band Laplacian blend already present (not a missing reimplementation)  
- Overmix as **external** tool only (GPL-3.0)  

### 10.3 Explicit non-adoptions

UDIS++/SRStitcher wholesale; VidPanos hallucination risk; warp α > 0.5 on raw flow; mpdecimate for anime telecine; ToonCrafter without LPIPS/CLIP gate; linking Overmix; gate factories; default-OFF flag sprawl without scheduled A/B.

### 10.4 Vetted-but-unused directions (research)

- SEA-RAFT finetuned on LinkTo-Anime; AnimeInterp SGM  
- SAM-2 after validation gates  
- Joint seam+exposure formulations  
- Modified Poisson + MTOR if colour bleeding appears  
- OBJ-GSP / SemanticStitch as stretch  
- Datasets: ATD-12K, AnimeRun, LinkTo-Anime, PaintBucket-Character, Sakuga-42M  

---

## 11. Roadmap Landscape

### 11.1 Structure (as of analysis)

`docs/moon/ROADMAP.md` (~1,236 lines) combines:

- Full-corpus checkpoints and session archaeology  
- Product scope §0 (mobile deleted, QML deleted, Tauri frozen, Hybrid elevated)  
- Ground rules  
- Research base §R  
- Phases 0–6 + parked + anti-goals  
- Phase 5.1 bounded RL / math-opt reintroduction  

`docs/moon/CHANGELOG.md` notes that detailed S1–S266 session history was **not migrated** from the pre-import standalone repo; many roadmap “see CHANGELOG SNNN” citations are dead.

### 11.2 Phase status (condensed)

| Phase | Theme | Status snapshot |
| --- | --- | --- |
| 0 | Measurement foundation | Tools largely done; **human rating pass open**; Overmix/Hugin/SI-FID largely done |
| 1 | Targeted research gathering | Largely done; Overmix AnimationSeparator rejected as phase detector |
| 2 | Coherence-first core | Several A/Bs measured; defaults still OFF pending human ratings; some rejects |
| 2.6 | Bench host freeze | Fixed and full-corpus confirmed |
| 3 | Photometric & seam parity | Joint gain mixed/OFF; GraphCut rejected; multi-band already present; ToonOut fixed/default |
| 4 | Convert fallback classes | Triage done; borderline photometric diagnosis ongoing; exit gate not met |
| 5 | Exceed (SR, mesh seams, gen) | Stretch; unscheduled |
| 5.1 | Bounded RL / opt | Allowed only after Phase 4; prior RLHF/DRL deleted for process failure |
| 6 | Tutorials & onboarding | 6.1–6.3 largely shipped; assisted suggestions partial |

### 11.3 Roadmap process debt

Ground rule: roadmap ≤ ~350 lines. Current file is a **session log + plan hybrid**. It is excellent institutional memory and poor **product navigation**. Recommended future split (pending stakeholder brainstorm):

- Short `ROADMAP.md` (decisions + next actions)  
- `CHANGELOG.md` (shipped)  
- `docs/moon/history/` or `.agent/cache/` (postmortems & checkpoints)  
- Optional separate `product.md` / `pipeline-quality.md` / `infra.md`  

---

## 12. Packaging, Coupling & Standalone Readiness

### 12.1 Package naming confusion

Python code simultaneously uses:

- `asp_backend.*` (loaded via path hacks / aliases in benchmarks and tests)  
- `backend.src.*` (constants, errors — often resolving to **Image-Toolkit’s** packages)  

This exists to avoid namespace collisions when both repos share top-level names `backend` and `gui` (issue #3 family). It works in some environments and breaks CI/collection in others.

### 12.2 Dependency direction (problem)

**Ideal (standalone product):** Image-Toolkit depends on ASP.  
**Current (partial):** ASP depends on Image-Toolkit for:

- C++ headers + single `base` extension entry  
- `backend.src.constants` / `backend.src.errors` in multiple modules  
- Config paths / HITL dir under `image-toolkit` naming (`~/.config/image-toolkit/hitl_sessions`)  

### 12.3 Workspace packaging

- Root `pyproject.toml`: uv workspace, `package = false`, members `backend`, `gui`  
- `backend` package name: `anime-stitch-pipeline`  
- Optional extras: `matchers`, `benchmark`, `benchmark-eval`, `dev`  
- GUI package: `anime-stitch-pipeline-gui`  

### 12.4 Standalone readiness checklist

| Requirement | Status |
| --- | --- |
| Own installable Python package with stable import name | Partial (`asp_backend` alias, not clean) |
| Own constants/errors vendored | Missing / parent-coupled |
| Own native module (pybind) | Missing (uses parent `base`) |
| Own README that describes the product | Partial (template residue) |
| Own CI green without parent PYTHONPATH | Fragile |
| Desktop entry / packaging (AppImage, etc.) | Not productised as ASP-only |
| GPU optional for Hybrid-only use | Plausible; auto ML needs GPU for serious speed |

---

## 13. GUI, Frontend & Meta-Infrastructure

### 13.1 GUI structure

- `gui/src/tabs/stitch_tab*.py` + many mixins/panels under `gui/src/elements/`  
- HITL dialogs: mask review, edge review, seam painter/diagnostic, landmark editor, canvas inspectors, etc.  
- Workers: stitch, match, canvas, batch, thumbs, etc.  
- Protocol pattern for mypy (`_stitch_tab_protocol.py`) mirrors backend pipeline Protocol fix  

Rough size: **~17k LOC** Python under `gui/src` — large relative to product polish, reflecting research UI growth.

### 13.2 Product-scope decisions (2026-08-06)

- Mobile deleted  
- QML deleted  
- Tauri frozen  
- Doc toolchains flagged for consolidation (MkDocs + Sphinx preferred)  

These were correct **opportunity-cost** decisions pre product-market-fit.

### 13.3 Template polyglot residue

Badges and AGENTS.md still advertise TypeScript, Kotlin, Java, Rust, Go modules as if this were a multi-language template. For ASP-the-product, that is noise. For ASP-the-submodule-inside-a-template-derived-monorepo, it is historical. Product docs should stop leading with unused languages.

---

## 14. Tutorials & Onboarding

| Item | Status |
| --- | --- |
| In-app Hybrid tour | Done |
| Docs Hybrid walkthrough | Done |
| Docs pipeline overview | Done |
| Bundled sample sequences | Done (synthetic SFW) |
| Assisted in-context suggestions | Partial / emerging |
| Video tutorials | Not observed as first-class |
| Auto-pipeline interactive tutorial | Thin relative to Hybrid |

Tutorials now exist; they are **not** the long pole. Trustworthy auto assistance and coherent defaults are.

---

## 15. ML, Optimisation & Deferred Ambitions

### 15.1 Present in tree

- Matcher wrappers: EfficientLoFTR, ALIKED+LG, RoMa, JAMMA, …  
- Masking: BiRefNet / ToonOut, SAM-2 paths  
- Flow: SEA-RAFT / DIS-style paths  
- `models/stitch_net.py`, `stitch_trainer.py`, `stitch_losses.py` — training stack presence  
- Optional research extras  

### 15.2 Deleted in great trim (for cause)

MFSR (DCT/PSO/DRL/diffusion SR), full RLHF stack, ToonCrafter seam synthesis, SRStitcher fill, Real-ESRGAN post, ProPainter bg completion, large gate factories, ~90 default-OFF experiment flags, etc.

**Important distinction:** deletion is evidence that those systems were **used without measurement discipline**, not proof that RL/opt can never help.

### 15.3 Phase 5.1 reintroduction policy (sound)

Only narrow, bounded, post-Phase-4:

1. RL for **pose-consistent frame selection** (highest leverage if reward = human coherence)  
2. PSO/genetic search over **few gate thresholds / warp weights**  
3. Evolutionary search over **blend/photometric parameters** (lowest priority; may be architectural not tuning)  

Do **not** resurrect RLHF-for-compositing or DRL-SR in prior form without re-justification.

### 15.4 Best product-shaped ML path

Rather than “fully automatic end-to-end,” the mission is better served by:

1. Auto **proposals** inside Hybrid (control points, seams, masks)  
2. Human corrections logged via HITL sessions  
3. Offline learning from those corrections  
4. Selection policies trained on human preferences once ratings exist  

This is progressive automation with a truthful UX, not a claim of solved auto stitching.

---

## 16. Pros — What to Keep (and Why)

| Keep | Why |
| --- | --- |
| Domain model (fg/bg, single-pose, no conflicting average) | Correct science for cel animation pans |
| Ground rules & anti-goals | Prevents pre-trim metric theatre |
| 97-test corpus + harness + comparators | Strategic asset; expensive to rebuild |
| Human > metric culture | Only coherence definition that matches “artist would keep this” |
| C++ kernels for hot paths | Right performance boundary |
| Matcher cascade + optional heavy deps | Practical degradation on flat cels / varied hardware |
| HybridStitch as first-class surface | Real user value today |
| Research docs + postmortems | Rare-quality institutional memory |
| Guarded SCANS fallback | Protects users from catastrophic composites |
| ToonOut/BiRefNet masking path | Domain-appropriate segmentation |
| GNC-TLS BA | Robust to match outliers |
| Onboarding wizard + samples + basic tutorials | Aligns with beginner-education mission |
| Thread-cap / resource guards on bench | Makes long experiments operable |
| Freeze second UI until quality gate | Opportunity-cost control |

---

## 17. Cons — What Hurts (and Why)

| Con | Why it matters |
| --- | --- |
| Auto pipeline still misses human coherence goal | Core automated promise unfulfilled |
| Phase 0.1 ratings uncollected | Blocks default flips, calibration, honest RL rewards |
| Selection/phase ceiling unsolved | Downstream work polishes already-lost cases |
| ~56% fallback rate | “Auto” often not the full pipeline |
| Not standalone | Blocks independent release, CI hermeticity, contributor onboarding |
| Dual `asp_backend` / `backend.src` namespaces | Fragile imports; issue #3 class failures |
| ~86 `ASP_*` flags vs ≤50 budget | Config surface exceeds own governance |
| Roadmap ~1236 lines vs ≤350 | Plan buried in session log |
| README/AGENTS template residue | Misrepresents product to humans and agents |
| Weak e2e regression for `run()` outside GPU corpus | Refactors are high-risk |
| Auto ↔ Hybrid handoff thin | Two tools, not one assisted workflow |
| ML/opt marketing ahead of default path | Vision/docs can oversell shipped capability |
| Large GUI surface vs product polish | Maintenance cost without proportional UX clarity |
| Parent-coupled C++ | Submodule cannot claim independent core |

---

## 18. What to Change — Options Matrix

Constraints intentionally dropped: stack, Image-Toolkit architecture, and “must preserve every flag.”

### 18.1 Product strategy

| ID | Avenue | Idea | Tradeoff |
| --- | --- | --- | --- |
| A1 | Hybrid-first v1 | Ship studio; auto is Assist | Fastest real product; auto research continues |
| A2 | Auto-first research | Phase-4 human parity before product claim | Coherent science; may delay ship |
| A3 | Two binaries | `asp-studio` + `asp-lab` | Clear packaging; dual release |
| A4 | Assisted Hybrid | Auto proposals into Hybrid with undo | Best mission match; needs handoff protocol |

**Analyst lean:** A4 or A1 as product spine; keep A2 as research track with honest status.

### 18.2 Measurement

| ID | Avenue |
| --- | --- |
| B1 | Owner runs rating pass on inspector (~45–90 min) |
| B2 | Multi-rater with existing schema |
| B3 | Train coherence model only after labels |
| B4 | Public SFW subset for CI/docs screenshots |

### 18.3 Selection / phase (highest algorithmic leverage)

| ID | Avenue |
| --- | --- |
| C1 | Redesign selection DP for bg-consistent, phase-pure subsets |
| C2 | Multi-phase → N short stitches + hard cuts (Hybrid merge) |
| C3 | Supervised ranker from human-preferred subsets |
| C4 | Bounded RL selection after C1 fails + labels exist |
| C5 | Productise “best single-phase reconstruction” mode |

### 18.4 Standalone architecture

| ID | Avenue |
| --- | --- |
| D1 | Soft standalone: vendor constants/errors; single import name |
| D2 | True `asp_native` pybind; toolkit consumes ASP |
| D3 | Process isolation (CLI/gRPC worker + thin GUI) |
| D4 | App monorepo layout; delete template polyglot noise |

**Analyst lean:** D1 immediately; D2+D3 as architecture north star.

### 18.5 Language / performance

| ID | Avenue | When |
| --- | --- | --- |
| E1 | Status quo+: Python + C++ + Torch | Default until PMF |
| E2 | Expand C++ orchestration of warp/seam/gain | Profile-proven hotspots |
| E3 | Rust middle layer | Packaging/safety priority |
| E4 | Full C++ Qt rewrite | Only after PMF + proven need |
| E5 | Custom GPU kernels | After profiling shows need |

**Analyst lean:** E1/E2. Full rewrites do not buy coherence.

### 18.6 Config & pipeline structure

| ID | Avenue |
| --- | --- |
| F1 | Profiles: `safe` / `quality` / `lab` |
| F2 | Delete unmeasured flags after TTL |
| F3 | Typed `PipelineConfig` (env override only) |
| F4 | Explicit stage graph object instead of monolithic `run()` |

### 18.7 Hybrid as ML-assisted studio

| ID | Avenue |
| --- | --- |
| G1 | Auto proposes CP/affines/seams |
| G2 | Corrections → training rows (HITL JSON) |
| G3 | Interactive anime-aware seam tools |
| G4 | In-context teaching only when suggestions are trustworthy |

### 18.8 Roadmap hygiene

| ID | Avenue |
| --- | --- |
| H1 | Short ROADMAP + CHANGELOG + history archive |
| H2 | Split product / pipeline / infra roadmaps |
| H3 | Kill pre-falsified items unless new evidence |

---

## 19. What Not to Do

Reaffirmed from anti-goals and critical evaluation:

1. No new quality gates without displacing an old one and a full-corpus run.  
2. No threshold-tuning sessions chasing ±0.002 SSIM.  
3. No new default-OFF flags without a same-session A/B plan.  
4. No Phase-2-era kitchen-sink ambitions (RLHF, 4K hybrid, generative seams) before Phase-4 exit.  
5. No trusting `asp_better` without looking at images.  
6. No second UI framework (Tauri/mobile) before product quality validation.  
7. No linking GPL Overmix into the binary; external process only.  
8. No treating GT-SSIM as a coherence metric.  
9. No full language rewrite as a substitute for selection/measurement work.  
10. No silent dependency on Image-Toolkit for “standalone” claims.

---

## 20. Recommended Priority Stack

If ASP is treated as a **standalone desktop product** with the stated mission:

1. **Complete Phase 0.1 human coherence ratings** (unblocks science and honesty).  
2. **Standalone packaging pass** (D1): stable package name, vendored constants/errors, honest README.  
3. **Declare product spine** (A1/A4): Hybrid-first or Assisted Hybrid in writing.  
4. **Auto → Hybrid handoff** of geometry/seams/masks/phases.  
5. **Selection / phase architecture** (C*), not more seam micro-opts.  
6. **Config profiles + flag cull** (F*).  
7. **Roadmap split** (H*).  
8. **Plan `asp_native` extraction** (D2) so C++ is truly owned by ASP.  
9. **Only then** bounded ML/opt (selection policy, Hybrid suggestions, optional threshold search).  
10. **Phase 5 “exceed”** (SR, mesh seams, generative) only after human parity exit gate.

If ASP is treated only as an **Image-Toolkit research submodule**, reverse 2/8 priority relative to toolkit integration—but still do 1, 5, and 6.

---

## 21. Open Questions for Stakeholders

*(Also delivered interactively; recorded here for permanence.)*

### Product & users

1. Primary user next 6–12 months (solo / small circle / public AGPL / commercial)?  
2. Definition of successful v1.0?  
3. Forever R18 corpus vs need for public SFW demo set?  
4. Vertical-only vs full 2D scroll for v1?

### Product hierarchy

5. Hybrid-first vs auto-first as non-negotiable spine?  
6. Importance of auto→Hybrid handoff vs isolated auto quality?  
7. SCANS fallback visible to users or silent safety net?

### Architecture & standalone

8. Priority of true standalone vs submodule-only life?  
9. Near-term Image-Toolkit integration goals?  
10. PySide6 forever vs eventual Tauri/web?

### Quality & measurement

11. Owner available soon for human rating pass?  
12. Prefer more SCANS safety vs more aggressive composites?  
13. Multi-output / multi-page per animation phase acceptable?

### ML / optimisation

14. First ML help domain (selection / mask / Hybrid seams / photometric / e2e)?  
15. Appetite for bounded RL/evolutionary work in the next year?  
16. Must-keep vs droppable optional models?

### Engineering constraints

17. CUDA required vs CPU Hybrid acceptable?  
18. Performance target (interactive vs batch)?  
19. License posture and refused dependencies?  
20. Aggression level on deleting flags/dead trainers/template scaffolds?

### Roadmap process

21. Preferred roadmap shape after decisions?  
22. Sacred vs killable roadmap items?

---

## 22. Appendix A — Approximate Size Inventory

Measured during analysis (approximate; excludes `node_modules`, venvs, massive website trees where noted):

| Area | Approx. LOC / scale |
| --- | --- |
| `backend/src` Python | ~18,000 |
| `gui/src` Python | ~17,000 |
| `backend/benchmark` Python | ~16,000 |
| `backend/test` Python | ~13,000 |
| `base/src` C++ | ~4,200 |
| Docs markdown (excl. website bulk) | ~4,200 |
| `.agent/cache` postmortems | ~1,400 |
| `docs/moon/ROADMAP.md` | ~1,236 lines |
| Unique `ASP_*` flag tokens in backend | ~86 |
| Backend test files (`test_*.py`) | ~32 files (many tests inside) |
| GUI test files | ~5+ |
| C++ Catch2 tests | 6 files |

Post-trim comparison (historical, state doc): animation Python ~30k → ~12.7k at trim time; flags 387 → 43 at trim; flags have grown again toward ~86.

---

## 23. Appendix B — Gate Set (Complete)

From post-trim state doc — keep this set small:

| Gate | Where | Effect |
| --- | --- | --- |
| Edge-graph connectivity | pre-BA | disconnected → SCANS |
| Affine validation + retry | Stage 7b | invalid → retries → PANORAMA → SCANS |
| dy_cv | post-BA | irregular scroll → SCANS |
| Horizontal scroll axis | Stage 9.5 | horizontal → SCANS / special path |
| Multi-frame coverage | post-render | sparse → SCANS |
| A6 single-pose escalation | per seam | large pose gap → one pose |
| Bench CompositeGate (SC/SB) | benchmark | banded render → SCANS output |
| Bench GhostGate + SeamVisGate | benchmark | ghost/hard-cut → SCANS output |

Rule: a new gate must **displace** an old one; nothing default-ON without full-corpus evidence.

---

## 24. Appendix C — Notable Env Flags

Non-exhaustive; full schema lives in `backend/src/core/config.py`.

**Selection / phase**

- `ASP_HOLD_AVERAGE`, `ASP_PHASE_AWARE_SELECT`, `ASP_PHASE_COMPOSITE`, `ASP_POSE_WINDOW_PX`, `ASP_TWO_CHANNEL_SELECT`

**Masking**

- `ASP_USE_SAM2`

**Seam / composite / photometric**

- `ASP_GRAPHCUT_SEAM`, `ASP_JOINT_GAIN_SOLVE`, `ASP_GLOBAL_GAIN_COMP`, `ASP_BG_AVERAGE`, `ASP_FG_REGISTER`

**Bench / ops**

- `ASP_BENCH_THREAD_CAP`, `ASP_BENCH_RAM_ABORT_PCT`, `ASP_BENCH_VRAM_ABORT_PCT`

Many experimental flags remain **default OFF** pending human ratings and full-corpus discipline.

---

## 25. Appendix D — Key File Index

| Path | Why it matters |
| --- | --- |
| `backend/src/core/pipeline/manager.py` | `AnimeStitchPipeline` composition |
| `backend/src/core/pipeline/run_stage.py` | 13-stage `run()` orchestrator |
| `backend/src/core/pipeline/_probes.py` | Optional dependency probes |
| `backend/src/core/config.py` | TOML/env schema |
| `backend/src/rendering/compositing/composite.py` | Stage 11 entry |
| `backend/src/ingestion/frame_selection/` | Selection + phase detection |
| `backend/src/ingestion/masking.py` | BiRefNet / SAM-2 masks |
| `backend/src/hitl/hitl_session.py` | HITL persistence |
| `gui/src/tabs/stencil/hybrid_stitch_panel.py` | Manual studio |
| `gui/src/tabs/stencil/onboarding_wizard.py` | First-run tour |
| `base/src/*.cpp` | Native kernels |
| `base/CMakeLists.txt` | Documents parent pybind coupling |
| `backend/benchmark/bench_anime_stitch.py` | Corpus harness |
| `docs/moon/ROADMAP.md` | Living plan + history hybrid |
| `docs/reports/ASP_Critical_Evaluation_2026-07-08.md` | Best single diagnostic of project pathology |
| `.agent/cache/asp_state_of_the_pipeline.md` | Post-trim pipeline truth |
| `docs/tutorials/*.md` | Beginner-facing docs |

---

## Closing Statement

ASP should be judged on two axes:

1. **As a research programme** to beat or match simple stitching on anime pans without tearing anatomy — disciplined, well-instrumented, still short of the exit gate, correctly cautious about default flips.  
2. **As a desktop product** for artists who need panoramas from scroll captures — HybridStitch + tutorials are the honest centre of gravity; full automation is an assistive subsystem that must **earn** trust under the project’s own ground rules.

The highest-leverage moves are not exotic: **rate the images**, **own the package boundary**, **choose a product spine**, **fix selection/phase**, **hand results to Hybrid for repair**. Language rewrites, second frontends, and resurrected RLHF stacks are distractions until those are done.

---

*End of report. Intended to be updated after the stakeholder brainstorm session and any subsequent roadmap rewrite.*
