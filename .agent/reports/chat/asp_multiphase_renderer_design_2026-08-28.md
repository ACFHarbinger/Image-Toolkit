# ASP multi-phase renderer — design proposal (for Harbinger sign-off)

**Author:** Claude
**Date:** 2026-08-28
**HEAD:** root `018a8ba1`, ASP `cdd9958`
**Relates to:** issue #463 (locked-slice renderer export review), ASP roadmap §2.2–2.4, `asp_change_roadmap_2026q3.md` "Known gap — P1 is unsafe for multi-phase sequences"
**Status:** design direction only. No code. Any benchmark validation named below goes through Codex with Harbinger authorization.

---

## TL;DR recommendation

Build **Option A — piecewise per-phase P1**: run the existing P1 plate compositor once per animation-phase span and join the results along the span boundaries, gated behind the existing default-off `ASP_PLATE_SINGLE_POSE` (piecewise auto-engages only when the sequence is multi-phase *and* passes a new contiguity check).

But do **one validation step first** (§4) that decides whether the whole approach is viable, and resolve **one spec question** (§5) about who owns cross-phase seams. Neither is code — the validation is a measurement Codex can fold into the next authorized sweep, the spec question is a decision for this document.

Do **not** ship any interim "route the skip through §2.3 instead of legacy" change — we cannot currently establish its baseline (§3, Option B).

---

## 1. Where multi-phase handling stands today

Three separate pieces of phase machinery already exist. They are not the same "phase":

| Piece | Flag | "Phase" means | What it does |
|---|---|---|---|
| **§2.2 phase detection** | always on (measurement) | dHash change-point over whole selected frames, `detect_animation_phases` → monotonic `phase_ids` in *selection order*; `phase_spans()` → `(phase, start, end)` | Feeds §2.3 and the P1 safety gate. Measurement-only for compositing otherwise. |
| **§2.3 phase-consistent compositing** | `ASP_PHASE_COMPOSITE=1` (default OFF) | same `phase_ids` | In the legacy seam loop: at any seam whose two frames are in different phases, skip midpoint-warp, escalate to single-pose from the dominant phase via `_dominant_frame_in_band`. Per-seam, local. Measured neutral-to-slightly-better; human ratings still open. |
| **P1 plate safety gate** | `ASP_PLATE_SINGLE_POSE=1` (default OFF) | same `phase_ids` + `source_has_multiple_phases` | `plate_single_pose_safe_for_phases` returns false for multi-phase → P1 skips, records `plate_single_pose_skipped="multiple_phases"`, **falls through** to M3/legacy seam path (Codex `c3931b93`; earlier `canvas.copy()` early-return bug caught by Agy). |
| **`_phase_clustering` / `_animation_repaint`** | internal to rendering | per-pixel FFT temporal-animation detection + KMeans edge-signature clustering → `phase_groups` (list of frame-index lists) | `_render_animation_repaint` re-renders **only the majority `phase_group`** over the canvas for cyclic animation. A different, region-level phase concept. |

**Net current behavior with P1 on:** 59/97 frozen-corpus cases (60.8%) are multi-phase (Agy's count) and get P1 skipped entirely. They fall to legacy compositing — which, if `ASP_PHASE_COMPOSITE` is also on, gets §2.3 seam treatment; otherwise vanilla legacy. The case-17 OOM / cross-phase-artifact class is **closed** by this gate (P1 default-off, skips cleanly).

**Sweep evidence (Codex, authorized, `05/36/51/67/73`, all RAW_ASP in frozen evidence):** arms were P1 vs P1+P2 — **not** `ASP_PHASE_COMPOSITE` on/off. With P1 on: `05/67` stayed `raw_asp`; `36` fell at `seam_vis_gate` (61.7 vs 35.0), `51` at `composite_gate_sb` (54.8 vs 35.0), `73` at affine validation. Peak RSS ~5 GiB, no OOM. This measures the **legacy fallback's quality on multi-phase**, not P1's ceiling — 3/5 don't reproduce frozen RAW_ASP through the fall-through path.

---

## 2. The specific gap

P1's model is **one canvas-aligned background plate + one hero foreground pose per connected zone** (`composite_plate_single_pose`, zone selection via `cv2.connectedComponents(union_fg)`). A multi-phase sequence has the character in two or more incompatible configurations across the pan. A single plate + single hero-per-zone either:

- picks one phase's pose and drops the others (missing action), or
- lets zones from different phases bleed into one plate (cross-phase ghosting / the case-17 artifact class).

Neither §2.3 nor `_animation_repaint` closes this:

- **§2.3** is a *seam-local* decision inside the legacy compositor. It never builds a clean plate; it just refuses to midpoint-warp across a phase boundary. It gives multi-phase cases the legacy seam-carve result with cleaner phase-boundary seams, not P1's clean-plate result.
- **`_animation_repaint`** re-renders *only the majority phase group*, explicitly discarding minority phases. That is a deliberate simplification for cyclic loops, not multi-phase pose-change coverage.

The gap is: **whole-canvas synthesis that gives each phase P1-quality treatment and stitches the phases together.**

---

## 3. Design options

### Option A — piecewise per-phase P1 *(recommended)*

**Partition.** Use `phase_spans(phase_ids)` → `[(phase, start, end), …]` in selection order. Each span is a contiguous run of selected frames in one phase.

**Per span.** Run the existing `composite_plate_single_pose` (plus P2/P3/P4 as configured) on *only that span's frames + their affines*, producing a per-phase plate + per-phase hero pose(s). This reuses the entire P1 stack unchanged — it just gets a shorter frame list.

**Join.** Composite the per-phase results onto the canvas in phase order, blending at the `n_phases − 1` span-boundary regions. Two candidate join mechanisms:

- reuse `_dominant_frame_in_band` / the legacy feather+Laplacian seam blend at each boundary row (consistent with §2.3's existing choice), or
- treat each per-phase plate as claiming a canvas band and let the last-writer-wins ownership map (P1 already produces a `claimed` map) resolve overlaps, with a feather at the band edge.

**Gating.** Reuse `ASP_PLATE_SINGLE_POSE`. Piecewise engages only when `source_has_multiple_phases` **and** the new contiguity check (§4) passes. `n_phases == 1` path is byte-identical to today. If contiguity fails or any span is too thin to build a stable plate (< ~3 frames), that sequence (or that span) falls through to legacy exactly as now — no regression versus current behavior.

**Why this is the target.** It is the only option that extends P1's actual benefit (clean plate, one coherent pose) to the 60.8% multi-phase majority, and it is mostly composition of code that already exists and is tested. It also lines up with M4 / Phase 5's "phase-group before alignment" direction (§6) as a concrete first step rather than a parallel mechanism.

**Risks.** (1) The contiguity assumption — see §4, this is the gate on the whole idea. (2) Per-span plate builds multiply compute/RSS by ~`n_phases` (sweep showed ~5 GiB for whole-sequence P1; a 3-phase case could approach ~10–12 GiB — needs a bounded check). (3) Boundary joins are a new seam class the metrics gates haven't seen; the joined result must clear `seam_vis_gate` / `composite_gate_sb` or it regresses to fallback like the sweep's `36/51`.

### Option B — route the P1 skip through §2.3 instead of vanilla legacy *(rejected for now)*

Superficially a cheap interim: when P1 skips for multi-phase, force `ASP_PHASE_COMPOSITE` behavior on the fall-through path so multi-phase cases at least get phase-consistent seams.

**Why not now:** we cannot state its baseline. Codex's `05/36/51/67/73` sweep did not record whether `ASP_PHASE_COMPOSITE` was set. If it was, §2.3 is *already* the fallback and B is a no-op. If it wasn't, the 3/5 regression figure isn't measuring the path B would ship. Proposing an interim whose baseline is unknown is worse than proposing only A. If Harbinger wants B considered, the prerequisite is: re-run the bounded sweep with `ASP_PHASE_COMPOSITE` explicitly on vs. off on the fall-through path, and report both.

### Option C — global plate + per-phase hero-cel exclusion

Keep one background plate for the whole canvas (camera trajectory is usually single-phase even when cel-pose isn't), but drive hero-pose selection from `_phase_clustering`'s `phase_groups`: for each animated region, pick one representative pose *per phase group* and place them in their respective canvas zones, excluding other phases' cels from the plate.

**Why lower priority:** it inherits `_phase_clustering`'s per-pixel FFT+KMeans detection (a second, independent phase notion from `detect_animation_phases`) and the reconciliation between the two is unspecified work. It also does nothing when phases genuinely need different *backgrounds* (parallax, lighting change across the phase boundary). Worth keeping as a fallback if A's contiguity check fails on most of the corpus — then per-zone exclusion is the only lever left short of M4.

### Option D — status quo + invest in §2.3 ratings

Leave the skip→legacy behavior as is (it safely closed case-17), and spend the effort getting `ASP_PHASE_COMPOSITE` its human coherence ratings so §2.3 can promote toward default-on for the legacy path. Multi-phase cases stay on legacy quality but with better seams.

**Why it's the floor, not the answer:** it accepts that 60.8% of the corpus never gets clean-plate treatment. Reasonable only if A and C both prove infeasible.

---

## 4. Load-bearing assumption — validate before building

**Assumption:** phase spans map to *contiguous vertical canvas regions*, so "stack the per-phase plates and blend at `n_phases − 1` boundaries" is well-defined.

**Why it's shaky:** `phase_ids` is monotonic in *selection order*, not in canvas `ty`. Canvas position comes from `affines[i][1,2]`. The §2.4 phase-aware-selection postmortem (2026-07-27, REJECTED) is about frame selection, not compositing, but its underlying finding is directly relevant: **phase structure and camera-step structure do not line up cleanly**, and a mechanism that assumed a clean local relationship changed a global outcome for the worse (test57: safe SCANS → visibly corrupt ASP). If a case pans back and forth, or phases interleave in selection order, the spans do not correspond to disjoint canvas bands and Option A's join is undefined for that case.

**Validation (measurement, not code — foldable into the next authorized Codex sweep):**
For a set of known multi-phase cases, for each: sort frame indices by `affines[i][1,2]` (canvas `ty`), then check whether `phase_ids` is still monotonic non-decreasing under that ordering. Report per-case: `n_phases`, whether spans are `ty`-contiguous, and max span overlap in canvas rows.

**Discriminating case set:** the frozen-corpus multi-phase cases that were **RAW_ASP** under legacy (Agy's list intersected with the ~20 multi-phase RAW_ASP cases Agy identified) — these are the ones piecewise P1 would actually be trying to improve. Start with the sweep five (`05/36/51/67/73`) since they already have frozen evidence and a bounded-RSS profile, then widen.

**Decision rule:**
- Spans `ty`-contiguous on a clear majority of the discriminating set → build Option A as specified.
- Contiguous on some, interleaved on others → build A with the contiguity check as a hard gate (non-contiguous cases fall through to legacy), and note expected coverage.
- Interleaved on most → Option A is not viable as a band-stack; fall back to Option C (per-zone exclusion, no band assumption) or D.

---

## 5. Spec decision — who owns cross-phase seams

§2.3 (`ASP_PHASE_COMPOSITE`) already owns cross-phase seams in the legacy path (`_fg_pose.py`, single-pose via `_dominant_frame_in_band`). Piecewise P1 also acts at phase boundaries. Two mechanisms, same seams, different logic. This document must pick one:

- **(a) Piecewise P1 owns boundary joins inside the plate path.** `ASP_PHASE_COMPOSITE` stays a legacy-path-only mechanism; when P1 is active and piecewise, the boundary join is P1's feather/ownership blend between two clean plates. Cleaner conceptually; the join is between two high-quality inputs.
- **(b) Piecewise P1 builds per-phase plates but defers the boundary join to §2.3's `_dominant_frame_in_band` logic.** Less new code, one blend implementation, but it means P1's output at the boundary is a legacy-style single-pose pick rather than a plate-to-plate blend.

**Recommendation: (a).** The whole point of A is plate-quality output; handing the boundary back to a legacy seam pick undercuts it. Keep §2.3 as the legacy-path mechanism it is today.

---

## 6. How this ties to M4 / Phase 5

Roadmap Phase 5 candidate #1 is "RL for pose-consistent frame selection … pick frame groups by animation phase," and M4 frames the architectural fix as "separate camera trajectory from cel-pose selection" / "phase-group before alignment." Both are **gated behind the Phase 4 exit gate** and need Phase 0.1 human coherence ratings that don't exist yet — not scheduled.

Piecewise per-phase P1 is the **compositing-side down payment** on that idea: it does "phase-group, then treat each group independently" at composite time, without touching frame selection (which §2.4 showed is where a greedy phase signal does damage). If it works, it also produces exactly the per-phase quality signal a later selection policy would need to train against. It does not pre-empt or conflict with the M4 selection work.

---

## 7. Open questions for Harbinger

1. **Flag surface:** reuse `ASP_PLATE_SINGLE_POSE` with piecewise auto-engaging (recommended, keeps the corpus story simple), or a distinct `ASP_PLATE_MULTIPHASE` sub-flag so P1-single-phase and P1-piecewise can be A/B'd separately?
2. **Compute ceiling:** is ~`n_phases` × the P1 plate build (potentially ~10–12 GiB RSS on a 3-phase case) acceptable for the benchmark host, or does piecewise need a hard `n_phases` cap (e.g. skip to legacy above 3 phases)?
3. **§5 spec decision:** confirm (a) — piecewise P1 owns boundary joins, §2.3 stays legacy-path-only.
4. **Validation scope:** is the §4 measurement OK to fold into the next authorized Codex sweep, or do you want it as a standalone bounded run first?
5. **Option B:** drop entirely, or authorize the `ASP_PHASE_COMPOSITE` on/off fall-through sweep to establish its baseline?

---

## 8. Effort & sequencing

1. **§4 validation measurement** (Codex, ~1 bounded sweep). Gate on the whole approach. *Blocks everything below.*
2. **Piecewise partition + per-span P1 invocation** — small; `phase_spans` + slice frame list + loop `composite_plate_single_pose`. Behind the existing flag, `n_phases==1` unchanged.
3. **Boundary join (§5a)** — the real work; plate-to-plate feather/ownership blend at span boundaries, must clear `seam_vis_gate` / `composite_gate_sb`.
4. **Contiguity + thin-span guards** — fall through to legacy when unmet; guarantees no regression vs. current skip behavior.
5. **Bounded corpus validation** (Codex, authorized) on the discriminating multi-phase RAW_ASP set. One change → one benchmark → keep or revert.
6. **No default-ON** without a full-97 run and Phase 0.1 human coherence ratings, per roadmap Ground Rules.

Steps 2–4 are one implementation delegation once step 1 clears and Harbinger has answered §7.
