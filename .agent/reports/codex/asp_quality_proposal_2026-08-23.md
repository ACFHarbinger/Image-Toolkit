# Raw ASP quality and re-routing proposal — 2026-08-23

## Decision frame

The frozen corrected evaluation says the immediate problem is render quality, not another rejector: Raw ASP shipped on 32/97 and only `asp_test67` is a clean example. The useful defect clusters are seam/blending (blur, seam line, banding) and content integrity (torn anatomy, duplicated strip, misordered content). Separately, 48/97 cases never produce Raw ASP because matching has no connected edge graph or no valid edge.

All candidates below are named, default-off experiments. They preserve Raw ASP, Safe ASP, and SCANS artifacts; none changes the post-match connectivity gate. Harbinger selects the validation IDs: 3–5 cases for each render cluster and 3–5 connectivity failures. No metric-derived subset is valid for promotion.

## Locked first slice — Harbinger/Codex, 2026-08-23

**Priority:** one coherent character pose comes before seam cleanup. P1 is therefore the first pixel-path candidate; P2 may refine only its already valid background plate.

**Seam/blending:** `asp_test03` (blur-only minimal case); `asp_test05`, `17`, `37`, `42`, and `78` (seam/banding without content-integrity defects).

**Content integrity:** `asp_test01`, `41`, `65`, `68`, `74`, and `82` (all three content defects plus the seam cluster); `asp_test28` and `83` (duplicated strip plus torn anatomy, without misordered content).

**Controls:** `asp_test67` is the clean Raw ASP regression guard; `asp_test73` is the near-clean torn-anatomy-only control. No candidate is promotable if it damages `67`.

**Connectivity:** `asp_test21`, `46`, and `52` are the assisted-recovery probes because the earlier offline overlap proposal found bounded bridge candidates for each. `asp_test89` is an anchors-too-sparse hard control; `asp_test25` is a separate genuine `no_valid_edges` control. `asp_test51` was removed because its frozen fallback reason is `seam_vis_gate`, not a connectivity failure. The set is deliberately mixed so a manual-assistance design must expose unresolved cases rather than turn them into silent acceptance.

## P0 — make the render path observable

**Mechanism.** Make the benchmark adapter report whether it invoked production-equivalent background normalization, with eligible-mask counts, background pixels, gains/clamps, residuals, and timing. Emit the same record for canvas-space joint gain and the background-plate builder when used. Keep pixels unchanged in this slice.

**Target.** All render clusters, especially ambient color shift.

**Why this is new.** Production has `_apply_background_photometric_normalization`, but frozen benchmark telemetry records zero corrected frames and no luminance/gain values in all 97 cases. This is an adapter-observability gap, not evidence that production correction is ineffective.

**Cost and cheap validation.** Low; fixture telemetry assertions plus the Harbinger-selected seam/blending slice. Promotion criterion is telemetry parity and a visible stage record, not an image-quality claim.

## P1 — background plate first, one foreground pose second

**Mechanism.** Build a canvas-aligned background plate only from pixels marked background across compatible frames, using a robust temporal estimator and canvas-space joint gain. Then composite exactly one selected foreground pose per region; never blend competing character poses. Expose a repair panel to paint a background/foreground correction, choose the hero pose, and accept/reject small inpaint holes. Save edits in the existing replay session as per-case constraints, not hidden image edits.

**Target.** Seam/blending and content integrity.

**Why this differs from existing ASP.** `coherence_v2` only assigns a single owner inside an overlap seam and is not the live default. Wallpaper mode has a plate builder, but Raw ASP's panorama renderer does not make the plate plus one-pose contract its independent candidate. This evaluates that whole renderer contract after alignment rather than tuning another seam threshold.

**Cost and cheap validation.** Medium. First prove source ownership and exact identity when disabled on synthetic layered pans, then render only the selected seam/content cases. Human review compares Raw ASP, candidate, and SCANS for severe defects and preference; no full bench until the slice has a clear gain without a new content-integrity regression.

## P2 — confidence-weighted two-source background reconstruction

**Mechanism.** Where a plate pixel has multiple aligned background samples, choose between a robust median and a seam-aware source label using local agreement, ink-edge preservation, and mask confidence. Flat regions can average to remove compression/flicker; around ink edges use one source so the output does not blur line art. The reviewer can pin a source or draw a no-average stroke in difficult zones.

**Target.** Blur, seam line, and banding.

**Why this differs from existing ASP.** Current seam and multiband machinery operates on strips, while `ASP_BG_AVERAGE` was harmful on mixed-phase, unaligned input. This candidate is conditioned on a canvas-aligned, background-only plate and explicitly has an edge-preserving source choice; it must not reuse the old unaligned average experiment under a new name.

**Cost and cheap validation.** Medium. Validate first on synthetic pans with known layers, then the selected seam/blending cases. Background agreement and line-edge spread are diagnostics; human review decides whether blur/banding improves.

## P3 — residual background-only local warp

**Mechanism.** After the existing global fit, estimate a regularized TPS or Moving-DLT residual from correspondences restricted to agreed background. Reject a residual with high bending energy or one moving protected foreground or straight-line regions; apply it to background samples only before P1/P2. Offer assisted point clicks when automation has too few reliable background anchors.

**Target.** Seam/blending caused by cel parallax, and part of the 48/97 matching/re-routing set.

**Why this differs from existing ASP.** APAP is available vendor prior art and UDIS2's useful geometric idea is a TPS residual on top of global warp. ASP is translation-first; this is a bounded background-only candidate, not a whole-frame non-rigid warp that can tear a character.

**Cost and cheap validation.** Medium-high. Start with synthetic planar plus two-layer parallax fixtures and a few artist-picked parallax cases. Require lower background residual and no new line-curvature/content defect in human review before any corpus run.

## P4 — segmentation uncertainty and trapped-ball alternate mask

**Mechanism.** Compute temporal disagreement between BiRefNet background masks after provisional alignment. In uncertain regions, derive a classical trapped-ball/line-art region map as an alternate background candidate; do not replace the learned mask globally. The user corrects only disputed regions with foreground/background strokes. Use agreed background for matching and plate samples; retain uncertain pixels as excluded rather than guessing.

**Target.** Content integrity and connectivity failures driven by foreground matches, especially flat cel art where a semantic mask is unreliable.

**Why this differs from existing ASP.** ASP has background masks but not a mask-reliability contract or a classical structural alternate used only under measured disagreement. Trapped-ball is a conservative region proposal, not a claim that every anime outline is closed.

**Cost and cheap validation.** Medium. Test synthetic broken-outline cases, then a small Harbinger-picked set with obvious mask errors. Track agreed and uncertain pixels and whether assisted corrections improve the render; do not claim automatic fallback reduction without those cases.

## P5 — assisted connectivity repair, with reproducible priors

**Mechanism.** For `disconnected_edge_graph`/`no_valid_edges`, stop with an explicit review state: a human confirms frame order, selects at least two background correspondences, or marks a static-background region. Fit only a bounded translation/affine from those constraints, then return to the normal pipeline. Store per-series pan direction, protected cels, and static-layer priors in the existing HITL session schema. Do not silently weaken the gate.

**Target.** The 48 re-routed cases.

**Why this differs from existing ASP.** It creates a productive route through an otherwise hard stop with auditable human evidence, rather than a new automatic acceptance threshold. It can also produce sparse correction data for later matcher training.

**Cost and cheap validation.** Low-to-medium. Run only on Harbinger's chosen connectivity failures. Success is a valid raw render the reviewer calls acceptable; failure remains an explicit safe fallback. Record human minutes per recovery before deciding whether it belongs in the normal workflow.

## Recommended order

1. P0 telemetry parity and P5's minimal review-state/schema work.
2. P1 as the primary renderer experiment, with P2 as its seam-quality branch.
3. P4 where masks prevent P1 from obtaining credible background samples.
4. P3 only for cases with residual background parallax after P1/P4.

This deliberately avoids more classifier/gate calibration: routing alone cannot create a competitive compositor.
