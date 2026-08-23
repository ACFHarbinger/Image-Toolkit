# Scoping Report: Content-Plausibility & Anatomical Coherence Signals

**Date:** 2026-08-23  
**Status:** Scoped / Design Only (Analysis & Architecture)  
**Author:** Agy / Antigravity  

---

## 1. Problem Statement: Why Geometric & Photometric Signals Miss Catastrophes

In the ASP benchmark corpus, catastrophic failures like `asp_test04`, `asp_test06`, and `asp_test14` exhibit severe **torn anatomy, duplicated limbs, severed torsos, and misordered content**. 

However, existing automated telemetry gates fail to catch this failure mode:
1. **Geometric & Alignment Gates (`RegistrationRiskGate`, BA RMS, Cycle RMS, RANSAC inliers):** 
   - Optical flow (LoFTR / JamMa) and RANSAC find clean, mathematically consistent homographies / affines on background elements (or consistent tracking across animated features). 
   - Bundle adjustment converges tightly ($\text{BA RMS} < 3\text{ px}$, $\text{Cycle RMS} < 5\text{ px}$). 
   - The geometry is mathematically valid, but the *semantic content* composited onto the canvas is physically impossible.
2. **Photometric & Gradient Gates (`SeamVisGate`, `GhostGate`):**
   - When Stage 11 applies a seam cut through a character's chest or slices an arm across two frames in different animation phases, the Laplacian blend / color matching makes the boundary luminance continuous ($\text{seam\_visibility} \approx 1.8$).
   - Traditional sharpness and edge metrics suffer severe inverse correlation ($\rho = -0.47$ to $-0.60$) because severed ink lines and stepped body slices register as high-frequency "detail".

**The Fundamental Gap:** None of today's signals inspect whether the assembled character bodies maintain *semantic topological plausibility* (e.g. single connected torso, single head, unbroken limb kinematic chains, monotone spatial-temporal cel progression).

---

## 2. Theoretical Anatomy of Content Failures

In 2D cel animation pans, content-coherence collapses into three distinct structural defects:

```
                  ┌──────────────────────────────────────────────────┐
                  │          Content-Plausibility Failures           │
                  └──────────────────────────────────────────────────┘
                                    │
         ┌──────────────────────────┼──────────────────────────┐
         ▼                          ▼                          ▼
 1. Anatomical Tearing      2. Pose Duplication       3. Misordered Strips
 (Severed Silhouettes /     (Multiple heads/limbs     (Spatiotemporal inversion
  fractured ink topology)    across overlap seams)     along pan trajectory)
```

1. **Anatomical Tearing (Ink Topology Fracture):** When a seam cut traverses a character cel, continuous ink outlines are abruptly terminated, producing high endpoint densities on line skeletons and disjoint contour components within a single semantic body mask.
2. **Pose Duplication / Cel Mixing (Multi-Instance Overlap):** Multiple frames containing the same character cel in different animation phases are simultaneously painted onto the canvas, causing multiple heads, phantom limbs, or superimposed poses.
3. **Misordered Strips / Kinematic Scrambling:** Inconsistent frame ordering or inverted translation hops scramble body segments (e.g. waist placed above shoulders).

---

## 3. Architecture of a Dedicated Content-Plausibility Signal

We propose a four-tier composite signal: **`ContentPlausibilityEvaluator` (CPE)**, combining topological line-art continuity, foreground semantic instance count, and DINOv2 self-similarity embedding coherence.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   ContentPlausibilityEvaluator (CPE)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 1. Line Art Topological Fracture (LTF)                                      │
│    └─ Skeleton endpoint ratio & junction discontinuities in FG mask         │
│ 2. Semantic Instance Invariant (SII)                                        │
│    └─ Foreground connected component topology vs. single-pose ground truth  │
│ 3. Pose-Graph DINOv2 Temporal Monotonicity (PTM)                            │
│    └─ Semantic feature cosine distance along vertical/horizontal axis       │
│ 4. Boundary Silhouette Curvature Discontinuity (BCD)                        │
│    └─ Sharp derivative spikes in BiRefNet alpha contour normals             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Tier 1: Line Art Topological Fracture (LTF)
- **Mechanism:** Builds on `anime_metrics.py::line_art_fracture_score` but restricts computation strictly to the dilated BiRefNet foreground mask ($M_{\text{fg}}$):
  $$S_{\text{LTF}} = \frac{N_{\text{endpoints}}(M_{\text{fg}} \cap \text{Skeleton}) + 2 \times N_{\text{fragments}}(M_{\text{fg}})}{\text{Total Line Length (px)}} \times 10^3$$
- **Behavior on `asp_test04`:** In the intact single frame, ink lines form closed contours (low endpoints). In the torn composite, severed arms and torso cuts produce dozens of open dangling endpoints ($S_{\text{LTF}} > 45.0$).

### 3.2 Tier 2: Semantic Instance Invariant (SII)
- **Mechanism:** Evaluates connected component topology of the foreground mask $M_{\text{fg}}$ on the canvas relative to the source frames.
- **Invariant:** A single character in a vertical pan should produce exactly one contiguous bounding hull (or a known number of connected components matching source frames). 
- If the canvas foreground segmentation reveals disjoint duplicate features (e.g. 2 detected face bounding boxes or 3 disconnected arm segments separated by background corridors), $\text{SII}$ flags a hard `duplicate_pose_violation`.

### 3.3 Tier 3: Pose-Graph DINOv2 Spatiotemporal Monotonicity (PTM)
- **Mechanism:** Patch-level DINOv2 visual features extracted along the composite's primary scroll axis.
- **Formulation:** For sliced vertical strips $y_0 < y_1 < \dots < y_N$, compute cross-strip feature cosine similarity matrix $S_{ij} = \cos(f(y_i), f(y_j))$.
- **Behavior:** In a natural anatomically coherent character, self-similarity exhibits smooth block-diagonal structure (head $\to$ torso $\to$ legs). In torn/misordered composites (`asp_test04`), severe off-diagonal blocks appear where legs or torso are repeated or inverted.

### 3.4 Tier 4: Boundary Silhouette Curvature Discontinuity (BCD)
- **Mechanism:** Examines the boundary curve $C(s)$ of the foreground character silhouette across seam transitions.
- Evaluates first and second derivatives of the boundary tangent angle $\theta(s)$:
  $$D_{\text{BCD}} = \max_{s \in \text{Seams}} \left| \frac{d\theta}{ds} \right|$$
- Stepped seam misalignments create $90^\circ$ non-differentiable silhouette notches (shear steps) that are physically unnatural in human/anime figures.

---

## 4. Signal Integration & Policy Placement

Where does this signal fit in ASP?

```
┌──────────────────────────────────────────────────────────┐
│                   Pipeline Flow & Gates                  │
│                                                          │
│  Stage 5/6: Pairwise Matching & Filtering                │
│  Stage 7:   Bundle Adjustment                            │
│  Stage 7b:  RegistrationRiskGate (Geometric/BA filter)   │
│             └─ Validates affine & graph health           │
│  Stage 11:  Compositing (coherence_v2 / Laplacian)       │
│  Stage 12:  ContentPlausibilityGate (Post-Composite)     │
│             ├─ Evaluates LTF, SII, PTM, BCD              │
│             ├─ If Plausibility Score < Floor:            │
│             │   └─ Escalate to SCANS / HITL Prompt       │
│             └─ Telemetry exported to session             │
└──────────────────────────────────────────────────────────┘
```

1. **Placement:** Post-Stage 11 pre-render evaluation (`ContentPlausibilityGate`).
2. **Decision Surface:**
   - **Low Risk:** $S_{\text{LTF}} < 25.0$, zero duplicate instance violations, smooth boundary curvature. $\to$ Safe for publication.
   - **Uncertain:** $25.0 \le S_{\text{LTF}} \le 40.0$. $\to$ Mandatory HITL review prompt.
   - **High Risk (Catastrophe):** $S_{\text{LTF}} > 40.0$ or duplicate instance detected. $\to$ Hard fallback to SCANS or single-pose handoff.

---

## 5. Summary & Verification Plan

| Metric Component | Target Failure Mode | Current Status | Next Step |
|---|---|---|---|
| **LTF** (Line Art Fracture) | Torn anatomy, severed limbs | Implemented in `anime_metrics.py` ($\rho = +0.320$) | Restrict to BiRefNet foreground mask ROI |
| **SII** (Semantic Instance) | Multi-pose mixing, duplicated heads/arms | Scoped | Prototype connected component counter on FG mask |
| **PTM** (DINOv2 Monotonicity) | Misordered slices, frame inversion | Scoped | Benchmark patch embedding cosine matrix |
| **BCD** (Boundary Curvature) | Shear steps at seam boundaries | Scoped | Prototype contour curvature derivative check |

This provides the exact mathematical and architectural foundation to systematically detect and reject content-coherence catastrophes like `asp_test04` without relying on geometric proxies.
