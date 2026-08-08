# ASP Proposed Roadmap (Grok draft)

**Status:** Draft proposal for multi-agent merge — **not** the authoritative `docs/moon/ROADMAP.md` yet.  
**Author:** Grok  
**Date:** 2026-08-08  
**Inputs:**

- Code/docs analysis: `.agent/reports/grok/asp_comprehensive_analysis_2026-08-08.md`
- Stakeholder answers (product, hierarchy, architecture, measurement, ML, engineering, roadmap process)
- Existing ASP artifacts: `submodules/ASP/docs/moon/ROADMAP.md`, critical evaluation, postmortems, state-of-pipeline

**Audience for this draft:** Owner + peer agent proposals (Claude/Gemini/Chat/…); later joint session produces the final roadmap(s) and GitHub issues.

---

## 0. Product contract (stakeholder-locked)

These are **non-negotiable product decisions** from the 2026-08-08 Q&A. Implementation details may change; these goals should not without an explicit revisit.

| # | Decision |
| --- | --- |
| P1 | **Near-term users:** owner + at most a few friends/researchers. No marketing-driven scope. |
| P2 | **v1.0 quality gate:** ASP matches or exceeds OpenCV Stitcher on **image quality and coherence** (no disjointed body parts, no out-of-order strips, etc.) on **nearly all** benchmark tests, as judged by the owner. Auto path: **zero human effort, or at most manual frame selection**. |
| P3 | **Primary product identity:** **HybridStitch as the human-empowering spine.** Best quality comes from human edits of intermediate/final outputs **plus** ML/RL and mathematical optimisation. Full auto is necessary for release metrics and labour reduction, not the only definition of success. |
| P4 | **Auto → Hybrid handoff > isolated auto polish** when priorities conflict (both matter; handoff wins ties). |
| P5 | **SCANS fallback remains user-visible**, but the objective is to fall back **as little as possible**. Prefer aggressive true composites over over-safe fallbacks once coherence risk is managed. |
| P6 | **Horizontal and diagonal scroll are MUST-have** (not parked indefinitely). Vertical-only is a temporary engineering subset, not the product end-state. |
| P7 | **Multi-output / multi-page** (e.g. one panorama per animation phase) is **acceptable** product behaviour. |
| P8 | **SFW public corpus:** wanted for CI/docs later; **only after** ASP is decent on the current (NSFW-sourced GT) bench. Do not block quality work on SFW procurement. |
| P9 | **UI strategy:** PySide6 stays for rapid GUI prototyping (and as an alternative desktop path). **Tauri is the release cross-platform app.** Image-Toolkit integration is a **plugin / launch-bridge** concern (even a “Launch ASP App” button is enough at the extreme). Standalone purity is **low priority**. |
| P10 | **Primary compute target:** CUDA-enabled devices. CPU-only Hybrid with degraded auto is acceptable. |
| P11 | **License:** AGPL + commercial dual license. |
| P12 | **ML/RL and mathematical optimisation are must-haves** (research workstream), with **frame selection as first ML priority** (also usable to help OpenCV and other stitchers, not only ASP internals). High appetite for RL/math-opt on selection after human ratings + classical parity progress. |
| P13 | **Options richness:** prefer offering many user-selectable algorithms/models over aggressively shrinking the stack. Cull default-OFF flags and dead trainers by **owner judgment of output quality**, not by dogma alone. |
| P14 | **Tracking:** final plan lives in roadmap(s) **and** GitHub issues; single vs split roadmap files decided in joint finalisation. |

---

## 1. North-star metrics

### 1.1 Release gate (v1.0)

Owner human verdict on the 97-test corpus (or the then-current full bench):

- **Coherence:** no catastrophic failures (torn anatomy, duplicated limbs/faces, misordered strips) on **nearly all** tests.  
- **Parity:** ASP output ≥ OpenCV Stitcher (SCANS/simple path as currently defined in the harness) on quality+coherence for nearly all tests.  
- **Automation:** that bar is met with **no human effort**, or **only manual frame selection** (not full Hybrid seam painting required for the gate).  
- **Fallback rate:** SCANS fallback **visible** when used, and **minimised** over time (aggressive composites preferred once coherence holds).

Automated metrics (GT-SSIM, sharpness, ghosting_siqe, seam_visibility, SI-FID, …) remain **diagnostics**. They never override owner coherence judgment (Ground Rule #2 retained).

### 1.2 Product success (ongoing, not only v1.0)

- HybridStitch can take auto intermediates (affines, matches, masks, seams, phase labels, multi-outputs) and improve them with less total labour than pure manual.  
- Frame-selection assistance improves **ASP and OpenCV** paths.  
- ML/RL/math-opt features exist as real, measurable tools (not roadmap vapour), starting with selection.

### 1.3 Explicit non-goals (near term)

- Public marketing site polish, app-store push, mobile apps.  
- SFW corpus procurement **before** bench competence (P8).  
- Perfect standalone packaging / decoupling from Image-Toolkit (P9).  
- Deleting optional models “to simplify” against owner preference for max options (P13) — cull only when quality judgment says dead weight.

---

## 2. Ground rules (carry forward, lightly updated)

Inherited from the post-trim culture; still non-negotiable:

1. **One change → one benchmark → keep or revert.** 5-test verify per change; full 97 before default flips that affect v1.0 path.  
2. **Owner visual verdict outranks every metric.**  
3. **Budgets (soft, re-negotiable in final merge):** prefer ≤ ~10 always-on gates; roadmap body short; experimental surface allowed as **user-visible options**, not as silent default-OFF landmines.  
4. **Owner owns priorities and quality calls; agents implement and measure.**  
5. **Postmortems for rejects** stay in `.agent/cache/` (or ASP equivalent); do not re-attempt without new mechanism.  
6. **Overmix stays external (GPL);** never link. Hugin stays comparator where usable.

**Update for P5 (aggressive composites):** gate thresholds may be **loosened or restructured** after human ratings exist, if the owner accepts more true composites that still pass coherence. Do not loosen gates blindly before the rating pass.

---

## 3. Workstreams (parallel tracks)

Four concurrent tracks. **Track Q is the release gate.** **Track H is the product spine.** **Track S is the research must-have.** **Track P is packaging/UI for release shape.**

```
        ┌─────────────────────────────────────────────┐
        │  Track Q — Quality & Coherence (v1.0 gate)  │
        └───────────────────┬─────────────────────────┘
                            │ feeds intermediates
        ┌───────────────────▼─────────────────────────┐
        │  Track H — Hybrid Studio + Auto handoff     │
        └───────────────────┬─────────────────────────┘
                            │ uses / trains
        ┌───────────────────▼─────────────────────────┐
        │  Track S — Selection + ML/RL/Math-Opt       │
        └───────────────────┬─────────────────────────┘
                            │ ships via
        ┌───────────────────▼─────────────────────────┐
        │  Track P — Prototype GUI → Tauri release    │
        └─────────────────────────────────────────────┘
```

Dependencies:

- **Human ratings (Q0)** unblock default flips and selection RL rewards.  
- **Selection (S)** unblocks quality (Q) and also helps OpenCV baseline experiments.  
- **Handoff (H1)** unblocks Hybrid as the empowerment loop.  
- **2D geometry (Q3)** is a hard product requirement (P6), not a stretch.  
- **Tauri (P2)** is release packaging; does not block algorithm progress.

---

## 4. Phase plan

Phases are ordered by **dependency**, not “only one phase at a time.” Items marked **∥** may run in parallel with the active critical path.

---

### Phase Q0 — Human coherence foundation *(critical path start; owner task)*

**Goal:** Make the success metric real.

| ID | Item | Owner | Done when |
| --- | --- | --- | --- |
| Q0.1 | Complete human coherence rating pass on current baseline (inspector / `asp-benchmark-assess`) | Owner (today/tomorrow) | Ratings file exists for full or large majority of corpus; catastrophic vs ok labels trustworthy |
| Q0.2 | Wire ratings into verdict veto + summary (if any gaps remain) | Agent | `human_coherence` fields + veto behaviour verified on real ratings |
| Q0.3 | Calibrate automated metrics vs human (rank correlation; demote liars to diagnostic-only) | Agent ∥ | Short report: which metrics agree with owner on coherence |
| Q0.4 | Publish a “coherence failure taxonomy” from ratings (pose/selection vs photometric vs seam vs order) | Agent ∥ | Taxonomy drives Q1–Q3 priority order |

**Exit:** Owner ratings exist; no default-path change claims “done” without checking them.

**Note:** This is the single highest-leverage item already identified in analysis and confirmed by the owner.

---

### Phase Q1 — Aggressive composite policy + honest fallback UX

**Goal:** Honour P5 — fewer SCANS fallbacks, more true composites, fallback still visible.

| ID | Item | Notes |
| --- | --- | --- |
| Q1.1 | Re-triage borderline `seam_vis_gate` / `composite_gate_sb` using Q0 ratings (not SSIM alone) | Many borderline cases are photometric (prior triage) |
| Q1.2 | Photometric fixes targeting owner-rated failures (joint gain re-measure, luminance-only gain, local band fixes) | Re-use postmortems; one change → one bench |
| Q1.3 | Gate policy revision under “aggressive composite” | May raise floors only with Q0 support; document each change |
| Q1.4 | UX: SCANS fallback always labelled in PySide6 (and later Tauri) with reason code | Visible fallback (P5) |
| Q1.5 | Multi-output mode for multi-phase sequences | Acceptable behaviour (P7); each phase = optional separate panorama |

**Exit:** Owner-rated coherence on true composites improves; fallback rate drops without a spike in catastrophic labels.

---

### Phase S1 — Frame selection first *(research + quality spine)*

**Goal:** P12 — selection is the first ML/math-opt priority; also feeds OpenCV and ASP.

| ID | Item | Notes |
| --- | --- | --- |
| S1.1 | Selection objective redesign: bg-consistent displacement + pose/phase purity (classical) | Beat rejected `ASP_PHASE_AWARE_SELECT` mechanism; new design, not flag flip |
| S1.2 | Export **selected frame sets** as first-class artifacts usable by: ASP pipeline, OpenCV Stitcher, Overmix/Hugin runners | Selection helps “other stitchers,” not only ASP (P12) |
| S1.3 | Bench: selection A/B scored by **Q0 human coherence of downstream stitch**, not GT-SSIM alone | Fixes GT-coupling pathology |
| S1.4 | Optional: hold averaging / phase-consistent selection re-measure after Q0 | Prior mixed results; re-open only with human scores |
| S1.5 | **Math-opt search** over selection hyperparameters (PSO/genetic/CMA-ES — pick one, keep small) | High appetite (P12); objective = human score or proxy calibrated in Q0.3 |
| S1.6 | **RL for selection** (bounded): policy proposes keep/drop or phase grouping; reward from human ratings / Hybrid accept-reject | Only after Q0; start offline / contextual bandit before heavy DRL |
| S1.7 | Hybrid UI: “selection assist” — show recommended subset, allow manual override (manual selection allowed for v1.0 gate) | Aligns with P2 + P3 |

**Exit:** A selection mode exists that improves owner-rated outcomes on a defined hard subset vs current default; frame lists are reusable by OpenCV path in bench and GUI.

---

### Phase Q2 — Match / BA / coherence-first assembly

**Goal:** Kill catastrophic upstream failures (wrong order, huge dy_cv, character-as-camera).

| ID | Item | Notes |
| --- | --- | --- |
| Q2.1 | Failure-class drive from Q0.4: fix matching/BA issues on catastrophic tests first | Critical eval family 07/34/43/77/82-class |
| Q2.2 | Phase-consistent compositing defaults re-evaluate under Q0 | Prior `ASP_PHASE_COMPOSITE` / hold average were measured but OFF |
| Q2.3 | Single-pose escalation / dominant-frame policy tuned for aggressive composites | Prefer one coherent pose over fallback when possible |
| Q2.4 | Preserve multi-band Laplacian; do not re-litigate “add multi-band” | Already shipped |
| Q2.5 | GraphCut only if fragmentation hypothesis addressed (anime edge cost / custom energy) | Prior rejects stand otherwise |

**Exit:** Catastrophic coherence failures rare on corpus; remaining losses are photometric/seam polish class.

---

### Phase Q3 — Full 2D geometry (horizontal + diagonal) **MUST**

**Goal:** P6 — horizontal/diagonal are release requirements, not parked forever.

| ID | Item | Notes |
| --- | --- | --- |
| Q3.1 | Design note: motion model + canvas for 1D vertical / horizontal / general 2D translation (and limited affine if needed) | Blast radius: canvas, warp, seam, coverage gates |
| Q3.2 | Remove “horizontal → immediate SCANS” as the only behaviour; implement true horizontal path | |
| Q3.3 | Diagonal / 2D scroll path with tests (synthetic + any real corpus cases) | Multi-output still allowed if single canvas is pathological |
| Q3.4 | Trajectory smoothing / wave correction revisit only after 2D canvas exists | Was parked with 2D; re-evaluate together |
| Q3.5 | HybridStitch control points / mesh already 2D-capable — ensure handoff and render respect non-vertical | Track H coupling |

**Exit:** Non-vertical sequences produce owner-acceptable panoramas on a defined test set without mandatory SCANS-only behaviour.

**Scheduling note:** Q3 can start design ∥ Q1/Q2, but large implementation should not starve S1 (selection) or H1 (handoff). Propose: **design early, implement after Q0 + S1.1 classical selection baseline**, unless 2D bugs block the owner’s daily use.

---

### Phase H1 — Auto → Hybrid handoff *(product spine; priority over isolated auto polish)*

**Goal:** P3–P4 — human empowerment loop.

| ID | Item | Notes |
| --- | --- | --- |
| H1.1 | Define handoff schema: frames, affines/homographies, match graph, masks, seams, phase ids, multi-outputs, fallback reason, stage dumps | Versioned JSON/sidecar |
| H1.2 | Pipeline export of schema after auto run (even on SCANS fallback — export what was attempted) | |
| H1.3 | Hybrid import: populate sequence + CP/affines + seam masks + colour suggestions | User can edit immediately |
| H1.4 | Round-trip: Hybrid edits re-enter late stages (re-seam / re-render without full re-match) where possible | Labour reduction |
| H1.5 | HITL session unification: auto checkpoints + Hybrid edits in one replayable session | Existing HITL JSON is a base |
| H1.6 | “Send to Hybrid” / “Re-run auto with my selection” buttons in PySide6 | Prototype first (P9) |

**Exit:** Owner can run auto, open Hybrid on the same case with intermediates preloaded, fix, and export — as the default advanced workflow.

---

### Phase H2 — Hybrid as assisted studio

**Goal:** ML/opt assist inside Hybrid without requiring perfect full auto.

| ID | Item | Notes |
| --- | --- | --- |
| H2.1 | Suggest control points / matches from auto matchers | User accepts/rejects |
| H2.2 | Suggest seams (DP path + optional interactive refine) with anime edge-cost bias | |
| H2.3 | Suggest masks / SAM-2 click refine with per-frame shapes correct | Issue-class fixes already partially done |
| H2.4 | In-context recommendations only when Q0-calibrated (trustworthy teaching) | Phase 6.4 vision |
| H2.5 | Sample projects + tutorials updated for handoff workflow | Keep SFW samples |

**Exit:** Hybrid is faster than pure manual for typical cases; assistance is optional (max options, P13).

---

### Phase S2 — Broader ML / math-opt (after S1 + Q0)

**Goal:** P12 must-have research, without repeating pre-trim RLHF pathology.

| ID | Item | Gate before start |
| --- | --- | --- |
| S2.1 | Expand selection RL/math-opt if S1.5–S1.6 win | Human-rated win on subset |
| S2.2 | Optional learnable rankers for seam/gain parameters (small search spaces first) | Prefer math-opt over end-to-end black box initially |
| S2.3 | Keep optional model zoo user-selectable (SAM-2, RoMa, SEA-RAFT, …) | Max options (P13); document GPU cost |
| S2.4 | Revisit stitch_net / trainers only if selection+Hybrid data pipeline produces real labels | Else delete dead trainers per owner quality judgment (P13) |
| S2.5 | Explicitly **do not** restore pre-trim RLHF/MFSR/diffusion stacks wholesale | New justification required each time |
| S2.6 | Research log: each ML/opt experiment → bench JSON + owner note + keep/revert | |

**Exit:** At least one selection-time ML or math-opt method is owner-validated and exposed as a user option; further methods accrete under the same discipline.

---

### Phase Q4 — v1.0 release gate campaign

**Goal:** P2.

| ID | Item |
| --- | --- |
| Q4.1 | Full-corpus owner rating of candidate default config |
| Q4.2 | Freeze default profile (`safe` vs `quality` naming TBD) that meets “nearly all ≥ OpenCV” |
| Q4.3 | Document residual failures (accepted multi-output or “needs Hybrid” cases) honestly |
| Q4.4 | Fallback rate report (visible SCANS reasons histogram) |
| Q4.5 | Manual-frame-selection-only path verified as sufficient for remaining hard cases where full auto still fails |

**Exit:** Owner declares v1.0 quality gate met.

---

### Phase P1 — Prototype GUI (PySide6) hardening ∥

**Goal:** P9 rapid prototyping path; Image-Toolkit plugin-light integration.

| ID | Item |
| --- | --- |
| P1.1 | Keep PySide6 Stitch + Hybrid as daily driver for feature tests |
| P1.2 | Image-Toolkit: ensure ASP surfaces under Image Stitch category; launch-bridge acceptable |
| P1.3 | Performance target instrumentation per sequence (wall time, VRAM peak) — P10/P18 |
| P1.4 | Profile-based presets (user-visible options), not only env flags |

---

### Phase P2 — Tauri release shell *(after algorithm confidence, not before)*

**Goal:** P9 release cross-platform app.

| ID | Item |
| --- | --- |
| P2.1 | Unfreeze `frontend/` only when Q-track shows sustained quality progress (recommend: after Q0 + H1.3 + S1.2 at minimum; ideally after Q4 for “1.0 app”) |
| P2.2 | Bridge protocol: local HTTP/IPC or CLI worker to Python/C++ pipeline (prefer process isolation for ML stack) |
| P2.3 | Port Hybrid-first UX + visible fallback + handoff; auto as Assist |
| P2.4 | Packaging for Linux primary; Windows/macOS as follow-ons |
| P2.5 | PySide6 remains alternative/prototype desktop |

**Exit:** Tauri app runs core Hybrid + auto assist workflows on CUDA hosts; not a second incomplete scaffold.

---

### Phase C1 — SFW public corpus *(after decent bench performance)*

**Goal:** P8.

| ID | Item |
| --- | --- |
| C1.1 | Define “decent” threshold (e.g. owner: catastrophic rate below X% on NSFW GT corpus) |
| C1.2 | Procure/build SFW scroll sequences + GT or human rankings |
| C1.3 | CI subset runs SFW only; full NSFW stays local/private |
| C1.4 | Docs screenshots from SFW only |

**Exit:** CI/docs no longer depend on NSFW assets.

---

### Phase X — Stretch (post-v1.0)

Only after Q4:

- Per-phase super-resolution / Overmix-style √N averaging  
- Anime SR finish models (optional)  
- OBJ-GSP / SemanticStitch-class seams  
- Generative fill behind LPIPS/CLIP gates  
- Deep toolkit integration beyond launch bridge (if ever desired)

---

## 5. Priority order (what to do next, concretely)

### Immediate (this week)

1. **Q0.1** — Owner human rating pass.  
2. **Q0.2–Q0.4** — Agents: ingest ratings, calibrate metrics, taxonomy.  
3. **H1.1** — Spec handoff schema (can draft while ratings run).  
4. **S1.1–S1.2** — Classical selection redesign + export selected frames for OpenCV/ASP.

### Short term (after Q0)

5. **Q1** aggressive composite + photometric borderline fixes guided by ratings.  
6. **H1.2–H1.6** handoff implementation in PySide6.  
7. **S1.5** math-opt over selection hyperparams; **S1.6** RL selection prototype if rewards stable.  
8. **Q3.1** 2D geometry design note (implementation queue after selection baseline unless owner blocked).

### Medium term

9. **Q2** catastrophic upstream fixes.  
10. **Q3.2–Q3.5** horizontal/diagonal implementation.  
11. **H2** assisted Hybrid.  
12. **Q4** v1.0 gate campaign.

### Release shape

13. **P1** continuous; **P2** Tauri when quality track justifies unfreeze.  
14. **C1** SFW corpus after “decent” on current bench.

---

## 6. Flag / options / trainer policy (P13)

| Policy | Detail |
| --- | --- |
| User-facing options | Prefer explicit GUI/CLI choices (matcher, masker, selection mode, composite aggressiveness) over hidden `ASP_*` env flags |
| Default-OFF env flags | Cull when owner judges no quality value on intermediate/final outputs; keep postmortem one-liners |
| Dead trainers / unused nets | Delete or quarantine when they do not affect quality path; reintroduce only with data from Hybrid/HITL |
| Optional models | Keep broad zoo (SAM-2, RoMa, SEA-RAFT, …) as install extras + selectable options; document cost |
| Experiments | Lab profile or CLI flags OK if documented and measured; no silent default changes |

---

## 7. Mapping: old roadmap → this proposal

| Old focus | Disposition in this proposal |
| --- | --- |
| Phase 0.1 human ratings | **Q0 — first critical path item** |
| Phase 2 coherence-first / phase composite | **Q1–Q2**, defaults after Q0 |
| Phase 4 fallback conversion | **Q1** under aggressive composite policy |
| Parked 2D canvas | **Q3 MUST**, not parked |
| Phase 5.1 RL/math-opt | **S1/S2**, selection-first, high priority after Q0 |
| Phase 6 tutorials | Keep; extend for handoff (H2.5) |
| Hybrid parallel track | **H1/H2 elevated** above isolated auto micro-opts |
| Tauri frozen until Phase 4 | Softened to **quality progress gate** (P2.1), Tauri = release app |
| Standalone packaging push | **Deprioritised** (P9) |
| SFW / public demo | **C1 after quality** |
| Roadmap ≤350 lines / single file | Final structure TBD in joint merge (P14); this draft stays under ~400 lines as a proposal |

---

## 8. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Aggressive composites reintroduce catastrophic tears | Q0 ratings + per-change visual; multi-output escape hatch |
| Selection RL before ratings = metric gaming | Hard gate: no S1.6 without Q0 |
| 2D geometry blast radius stalls quality | Design early; implement after selection baseline unless owner blocked daily |
| Tauri too early → second incomplete UI | P2.1 quality progress gate; PySide6 remains prototype |
| Max options → unmaintainable surface | Options allowed; **defaults** remain few and measured |
| NSFW corpus forever blocks CI | C1 after decent quality; private full bench stays local |
| Research appetite outruns gate discipline | S-track experiments stay option-flagged until Q4 default freeze |

---

## 9. Suggested GitHub issue epics (for joint finalisation)

Epics only — issue breakdown later:

1. `Q0` Human coherence ratings + metric calibration  
2. `S1` Frame selection redesign + export + math-opt/RL  
3. `H1` Auto→Hybrid handoff schema + UI  
4. `Q1` Aggressive composites + photometric borderline + visible fallback UX  
5. `Q2` Upstream match/BA coherence  
6. `Q3` Horizontal + diagonal 2D geometry  
7. `H2` Assisted Hybrid suggestions  
8. `Q4` v1.0 owner gate campaign  
9. `P2` Tauri release shell  
10. `C1` SFW CI corpus  
11. `S2` Extended ML/opt (post-selection wins)

---

## 10. One-paragraph summary for peer agents

ASP v1.0 is defined by **owner-judged coherence parity with OpenCV on nearly all bench tests**, with automation requiring at most manual frame selection — but the **product spine is HybridStitch**, fed by a first-class **auto→Hybrid handoff**, with **visible but rare SCANS fallbacks** and a preference for **aggressive true composites**. **Frame selection** is the first ML/math-opt battleground (also to boost OpenCV), with **high appetite for RL/PSO-style selection** only after the **imminent human rating pass**. **Horizontal/diagonal are mandatory**; multi-output is allowed; SFW corpus waits until quality is decent; **PySide6 prototypes, Tauri releases**; Image-Toolkit is a light bridge; AGPL+commercial remains; options stay rich while defaults stay measured. This draft is Grok’s merge input, not the final roadmap.

---

*End of Grok proposed roadmap — 2026-08-08.*
