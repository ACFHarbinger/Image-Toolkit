# `_blend_phase_plates` seam fix — direction (for Harbinger, post-coherence-rating)

**Context:** the 2026-08-29 sweep (`asp_multiphase_sweep_2026-08-29.md`) showed piecewise-P1 is mechanically sound and memory-safe, with 2 stable wins (test05, test41), but 6–7 engaged cases fail `seam_vis_gate` (asp_sv 44–145 vs limit 35) or `composite_gate_sb`. This is the blocker to piecewise-P1 being a quality win. No code yet — direction only, for sign-off when the coherence-rating pass is done.

## Root cause (high confidence)

`seam_visibility_score` = worst per-row mean-abs-luminance-difference spike. Values 44–145 mean a **horizontal luminance step at the phase-band join rows**, not a geometric tear (the join geometry is fine — reverse-pan handled, cels preserved verbatim, per Agy `9b6116a2`).

Where the step comes from: `composite_plate_multiphase` runs `composite_plate_single_pose` **independently per span**, so `_apply_joint_gain_solve` equalises gain *within* each span with prior `g_i → 1.0` but **there is no gain coupling across spans**. Adjacent plates end up at slightly different absolute brightness. `_blend_phase_plates` then alpha/Laplacian-blends them over a fixed ≤96 px band — which cross-fades the step but doesn't remove it, so a residual jump sits at `seam_y`. (Agy flagged exactly this in the S1/S2 review: "adjacent plates may show a small background-luminance step at the boundary that the join must absorb.")

## Direction

**Attempt 1 — cross-span photometric coupling (cheap, matches existing machinery).**
After all per-span plates are built, before the join loop: for each adjacent pair in `physical_phase_order`, measure the mean (or per-channel median) luminance of both plates over their **valid `ty` overlap band**, and apply a single global gain/offset to bring the later plate onto the earlier one's level (chain along the order). This is the same idea as `_apply_joint_gain_solve` but one coupling term per boundary instead of per-frame. ~20 lines, no new blend math. Re-run test05/08/41/67/71/72 and read `seam_vis`.

**Attempt 2 — gradient-domain join (if the step persists after 1).**
Replace the alpha/Laplacian blend in the background band (`both_bg & band`) with a 1-D Poisson / screened-Poisson reconstruction across the seam: keep both plates' gradients, solve for the values so the boundary has no discontinuity by construction. Cels (`claimed ≥ 0`) still copied verbatim, untouched. More code (~a small solver over the band rows), but robust to any residual offset and to local texture mismatch.

**Not recommended:** widening/shaping the feather adaptively — it smears the step over more rows rather than removing it, and a wide feather on real background texture reads as blur.

## Validation

- Unit: extend `test_blend_phase_plates_narrow_overlap_has_no_luminance_step` (already asserts max row-to-row delta ≤ 8) to a synthetic two-plate case with a **deliberate 15–20 luminance offset** between the plates and assert the joined seam delta stays bounded.
- Bench: the same 8 engaged cases from the sweep (`05,08,17,41,67,71,72,91`), `seam_vis` before/after. Target: the 4–5 currently in the 44–80 band drop under 35 and flip to `raw_asp`. Needs Harbinger auth (benchmark).
- The 2 existing wins (test05, test41) must not regress.

## Sequencing

Do this **after** the coherence rating on the current test05/test41 outputs — that rating is the reference for "is the seam actually the thing hurting perceived quality, or do the gates over-weight it." If the rated outputs already look good to a human despite passing the gate, the gate threshold may be the lever, not the blend.
