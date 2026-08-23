# ASP Milestone 5: Multi-Band / Laplacian Pyramid Blending Design

**Date:** 2026-08-23  
**Status:** Scoped / Design Only (Implementation Pending Review)  
**Author:** Agy / Antigravity  

---

## 1. Problem Statement & Motivation

In Stage 7 / Stage 11 compositing, adjacent video frames often exhibit subtle global and local photometric variations due to broadcast color grading, camera auto-exposure adjustments, or lighting gradients across horizontal/vertical anime camera pans.

The current baseline approaches have critical limitations:
1. **Hard Partition / DP Seam Cut:** Generates visible stepped luminance/color boundaries in flat background regions (e.g. skies, walls, gradients).
2. **Standard Alpha Feathers / Linear Ramps:** Causes noticeable ghosting / edge doubling in overlapping textured regions.
3. **Poisson Blending:** Causes severe color bleeding across high-contrast anime line art / ink outlines, destroying cel flat-color boundaries.
4. **Current `_laplacian_blend`:** Engages in Stage 11 seam zones (`_process_single_seam`), but is applied uniformly over the seam zone bounding box rather than strictly restricted to static background regions, risking high-frequency halo artifacts and color smearing across moving/contested cels.

**Goal for M5:** Adapt classical multi-band / Laplacian pyramid blending (as formulated by Burt & Adelson 1983 and utilized in Hugin / Enblend / OpenCV `MultiBandBlender`) specifically optimized for cel animation: smoothly blending low-frequency illumination gradients across wide spatial radii while strictly preserving high-frequency line art and isolating foreground character poses.

---

## 2. Theoretical Formulation

Given two warped, photometric-normalized source frames $I_A(x, y)$ and $I_B(x, y)$ and an effective background blend mask $M(x, y) \in [0, 1]$ (where $1.0$ indicates source $A$ and $0.0$ indicates source $B$):

### 2.1 Gaussian and Laplacian Pyramids
For level $l \in [0, K-1]$ (with default $K = \text{LAPLACIAN\_BANDS} = 5$):

$$\begin{aligned}
G_A^{(0)} &= I_A, \quad G_B^{(0)} = I_B, \quad G_M^{(0)} = M \\
G_A^{(l+1)} &= \text{pyrDown}(G_A^{(l)}), \quad G_B^{(l+1)} = \text{pyrDown}(G_B^{(l)}), \quad G_M^{(l+1)} = \text{pyrDown}(G_M^{(l)})
\end{aligned}$$

The band-pass Laplacian pyramids $L_A^{(l)}$ and $L_B^{(l)}$ are formed by subtracting the expanded lower-resolution level:

$$\begin{aligned}
L_A^{(l)} &= G_A^{(l)} - \text{pyrUp}(G_A^{(l+1)}), \quad 0 \le l < K-1 \\
L_A^{(K-1)} &= G_A^{(K-1)}
\end{aligned}$$

### 2.2 Frequency-Dependent Blending
At each scale $l$, the band-pass details are combined weighted by the corresponding scale of the smoothed mask $G_M^{(l)}$:

$$L_{\text{blend}}^{(l)} = L_A^{(l)} \odot G_M^{(l)} + L_B^{(l)} \odot (1 - G_M^{(l)})$$

The final composite image $I_{\text{composite}}$ is reconstructed by recursive upsampling and accumulation:

$$I_{\text{composite}} = \sum_{l=0}^{K-1} \text{pyrUp}^{(l)}(L_{\text{blend}}^{(l)})$$

---

## 3. Anime-Specific Invariants & Scope Boundaries

### 3.1 Strict Background Masking Invariant
- **Rule:** Multi-band pyramid decomposition and cross-band blending must operate **strictly on static background pixels** ($M_{\text{bg}} = \text{bg\_a} \cap \text{bg\_b}$).
- **Rationale:** Moving cels and characters have sharp boundary silhouettes. Blending character pixels across multiple pyramid scales causes ghost limb copies and blurred ink outlines. 
- Character regions ($M_{\text{fg}} = \sim M_{\text{bg}}$) bypass multi-band blending entirely and are resolved via the **M3 Single-Pose Compositor** (`coherence_v2` / `_fill_single_pose`), copying from exactly one source frame.

### 3.2 High-Frequency (HF) Detail Retention / Alpha Schedule
- In cel animation, black line art lives in the highest frequency band $L^{(0)}$.
- If low-frequency illumination drift is wide ($\pm 64\text{px}$ to $\pm 128\text{px}$ feather), blending $L^{(0)}$ broadly softens ink lines.
- **Solution:** Implement a **scale-dependent transition width**:
  - Lowest frequency bands ($l \ge 2$): wide, smooth transition across the entire overlap region ($\ge 64\text{px}$).
  - High-frequency band ($l = 0$): narrow transition tightly locked to the optimal DP minimum-cost seam line ($\le 4\text{px}$).

---

## 4. Integration Architecture in ASP

Multi-band background blending plugs directly into the compositing pipeline in `submodules/ASP/backend/src/rendering/compositing/`:

```
┌──────────────────────────────────────────────────────────┐
│                   Stage 11 Compositing                    │
│                                                          │
│  1. Warped Frames & BiRefNet Inverted Background Masks   │
│  2. M3 Foreground Single-Pose Region Assignment          │
│     └─ Resolves contested foreground cels to 1 pose      │
│  3. Stage 11 Background Multi-Band Blending (M5)         │
│     ├─ Low-frequency illumination blend on BG plate      │
│     ├─ High-frequency line-art seam cut on BG plate      │
│     └─ Gated behind ASP_MULTIBAND_BLEND (default OFF)    │
│  4. Paste Clean Single-Pose Foreground over BG Plate     │
└──────────────────────────────────────────────────────────┘
```

### 4.1 Proposed Config & Schema Flags
- `ASP_MULTIBAND_BLEND` (int, 0/1, default 0): Master flag enabling multi-band pyramid blending for background plate regions.
- `ASP_MULTIBAND_LEVELS` (int, 2-7, default 5): Number of Gaussian/Laplacian pyramid octaves.
- `ASP_MULTIBAND_HF_LOCK` (int, 0/1, default 1): Locks Level 0 detail to the discrete DP seam path to prevent line-art softening.

### 4.2 Module Locations
- `submodules/ASP/backend/src/rendering/compositing/_multiband.py`: Standalone, stateless multi-band pyramid blender with typed arguments, mask validity checking, and scale-dependent transition weighting.
- `submodules/ASP/backend/src/rendering/compositing/_fill.py`: Updated `_process_single_seam` and `_blend_or_single_pose_fill` to route background regions through `_multiband.py` when `ASP_MULTIBAND_BLEND=1`.
- `submodules/ASP/backend/test/rendering/test_multiband.py`: Isolated unit test suite covering pyramid reconstruction fidelity, boundary preservation, and mask edge invariants.

---

## 5. Falsifiable Verification & Safety Protocol

1. **Reconstruction Invariant:** For two identical input images $I_A = I_B$, multi-band blending across any arbitrary mask $M$ must satisfy $\max |I_{\text{composite}} - I_A| \le 1\text{ LSB}$ (exact numerical reconstruction).
2. **Pure Background Pan Screen:** On photometric pan cases exhibiting illumination steps across frame cuts (e.g. `asp_test28`, `asp_test96`), verify reduction in `seam_visibility_score` without degradation of `line_art_fracture_score`.
3. **No-Regression Invariant on Red Set:** When enabled alongside M3/M4, multi-band background blending must generate zero new crop losses and zero torn foreground cels.
4. **Execution Protocol:** Prototype tested purely with unit tests and small synthetic fixtures; any benchmark run must strictly follow the **Codex resource routing protocol** per `AGENTS.md`.

---
