# Image & Video Generation — Comprehensive Research Reference

*Consolidated 2026-06-03. This document is the single, complete reference for generative-model research in Image-Toolkit. It covers the entire field — the diffusion/flow mathematics, architecture lineages, conditioning, fine-tuning, the end-to-end character pipeline, inference frameworks, upscaling, the full video-generation stack, and hardware-aware deployment — with deep, dedicated sections on **anime image and video generation** (the project's target domain). It replaces the 5 prior generation reports listed in Appendix C; read this instead of them. Hardware reference: RTX 3090 Ti (24 GB) desktop, RTX 4080 (16 GB) / RTX 4080 mobile (12 GB).*

---

## Table of Contents

1. Scope & the One-Paragraph Recommendation
2. Mathematical Foundations (ε / v / x0-prediction, Rectified Flow, distillation)
3. Architecture Lineages (SD 1.5, SDXL, anime fine-tunes, MM-DiT/FLUX)
4. Conditioning & Prompting (tags, score-tags, natural language, Florence-2)
5. Fine-Tuning (LoRA, LyCORIS, DreamBooth, full FT, trainers, settings)
6. The End-to-End Character Pipeline (4K video → LoRA)
7. Inference Frameworks, Samplers, VAE, Control
8. Upscaling & Restoration
9. Video Generation — Temporal Injection Foundations
10. AnimateDiff (architecture, motion modules, MotionLoRA, anime fixes)
11. Interpolation & Inbetweening (AnimeInterp, ToonCrafter, ToonComposer)
12. Foundation Video Models (Wan2.1, SVD, DiT/SLRA)
13. Video Control & Long-Sequence Inference
14. Hardware-Aware Deployment (uv, TensorRT, quantization)
15. Implementation Status in Image-Toolkit
16. Appendices — model index, settings cheat-sheet, source reports

---

## 1. Scope & the One-Paragraph Recommendation

**Recommendation (2025–2026):** For the strongest combination of out-of-the-box anime quality, character knowledge, fine-tunability, and consumer-GPU friendliness, build the stack around **Illustrious XL v1.1/v2.0** (or its v-prediction sibling **NoobAI-XL v-pred**) as the SDXL-class base; train **rank-16–32 LoRAs** (LyCORIS LoCon for style-bound characters) with **kohya_ss/sd-scripts**; run inference in **ComfyUI** (Forge/reForge for fast iteration). The 3090 Ti trains LoRAs at full 1024² batch 2–4 and runs native FP16 FLUX; the 4080 trains at 1024² batch 1–2 with gradient checkpointing and runs FLUX only quantized. **FLUX.1** is the quality king for prompt adherence/text but a poor *primary* anime base (VRAM-heavy, slow to train, thin anime ecosystem) — keep it secondary. For video, use **AnimateDiff** (mature, controllable, model-agnostic) for short clips/GIFs and **ToonCrafter** for generative inbetweening; **Wan2.1/SVD** for longer foundation-model clips on 24 GB.

---

## 2. Mathematical Foundations

All these models are samplers of a learned probability transport from noise to data. The training-objective parameterisation is not cosmetic — it determines anime fidelity (especially flat/saturated palettes and pure black/white).

### 2.1 DDPM and ε-prediction
The forward process gradually adds Gaussian noise; as `t→T`, `q(x_t)` converges to isotropic `N(0,I)`. The reverse trajectory `p_θ(x_{t-1}|x_t)` is learned by a network. Because the exact reverse conditional is intractable, the standard objective is **ε-prediction** (noise prediction): `L = E‖ε − ε_θ(x_t, t)‖²`. **Weakness:** ε-prediction over-weights high-frequency noise at the expense of low-frequency compositional structure, so it underperforms on pure-colour backgrounds (absolute white/black) — exactly the critical anime case ("greyness"/washed-out gamut of base SDXL). Lineage: SD 1.5, SDXL-eps.

### 2.2 v-prediction (angular parameterisation)
To fix the SNR imbalance, **v-prediction** predicts a velocity vector `v = α_t ε − σ_t x_0` combining noise and data. The objective `L = E‖v − v_θ(x_t,t)‖²` converges faster and dramatically improves **dynamic range** — rendering stark high-contrast anime lighting. **NoobAI-XL V-Pred** uses exactly this to overcome SDXL "greyness." v-prediction also enables **progressive distillation**: a student matches a 2-step deterministic teacher, halving the probability-path traversal recursively, cutting NFEs from ~1024 to as few as 4 steps with minimal FID loss. Pair v-pred with **zero-terminal-SNR** for correct dark-scene/pure-colour fidelity.

### 2.3 x0 / optimal-transport prediction
A generalised target subsumes ε, v, and x0 as special cases. When ambient dimension ≫ intrinsic manifold dimension (compressed anime latents), **direct x0-prediction** is the analytically variance-optimal target. Frameworks like **k-Diff** learn the optimal prediction parameter directly.

### 2.4 Rectified Flow Matching (RFM)
The major 2024–25 shift: abandon stochastic Langevin dynamics for a **deterministic neural ODE** transporting mass along near-straight paths. For coupled `(x_0, x_1)`, linear interpolation `x_t = (1−t)x_0 + t x_1`; train a velocity field `v_θ` to regress the constant connecting vector via least-squares; generate by ODE integration (Euler/Heun). The **Reflow** operator recursively straightens trajectories → far fewer integration steps at equal fidelity. **Boundary-enforced RF** honours the `t=0/1` boundary conditions to reduce error near the data manifold. RFM is the backbone of **FLUX** and experimental **NoobAI-XL RF conversions** (ChenkinNoob-XL RF, Mugen) in the EQ-VAE latent — unlocking lighting/contrast fidelity impossible in EPS SDXL without offset-noise artifacts.

**Practical rule:** match the LoRA/training objective to the base (eps vs v-pred vs RF). Mixing (e.g. an eps LoRA on a v-pred base) degrades output.

---

## 3. Architecture Lineages

SOTA bifurcates into mature **2.6 B-param SDXL derivatives** and newer **12–32 B MM-DiT** rectified-flow models.

### 3.1 SD 1.5
Smaller U-Net, single CLIP encoder. Retained mainly for its mature **AnimateDiff** motion-module ecosystem (§10).

### 3.2 SDXL latent-diffusion backbone
Dual text encoders (**OpenCLIP ViT-bigG + CLIP ViT-L**) concatenated to cross-attend a much larger U-Net; **multi-aspect conditioning** generates varying aspect ratios without crop destruction. The anime workhorse.

**Anime SDXL fine-tunes:**
- **Animagine XL 4.0** — 2650 GPU-hrs on 8.4 M tagged anime images; cleanest line art, strict Danbooru-tag adherence. Mandates structured prompt order: `1girl/1boy, character, series, descriptions` + quality tags (`masterpiece, best quality, very aesthetic`). Optimised ~1024².
- **Illustrious XL v1.1 / 2.0** — first to natively support **1536 px** without compositional fracturing/anatomical cloning; hybrid tag + natural-language conditioning. **Caveat:** severe **token-dilution** — tokens late in its 248-token window are attenuated → front-load critical concepts. Does **not** understand score tags (degrades). Primary recommended base.
- **NoobAI-XL** (and v-pred) — divergent branch from Illustrious using v-prediction; superior stylistic versatility and character-knowledge retention. RF conversions exist (§2.4).
- **Pony Diffusion V6 XL** — 2.6 M aesthetically-ranked images (1:1:1 safe/questionable/explicit). Uses a proprietary **score-tag** system; due to a "Clever Hans" alignment failure, the model correlates the *presence of the verbose string* `score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up` with the highest-fidelity manifold — so that exact string is a rigid activation key (not a learned continuous range). Suppresses artist names. **Incompatible** with standard SDXL LoRAs/embeddings (diverged conditioning space).

### 3.3 MM-DiT — FLUX & Chroma
**FLUX.1** (Black Forest Labs) — 12 B **Multimodal Diffusion Transformer**; discards cross-attention concatenation for **parallel attention** over joint image+text tokens; replaces the secondary CLIP with a 9.4 GB **T5XXL** LLM for deep conversational prompts and spatial relations; rectified-flow transport. `FLUX.1 [dev]` (guidance-distilled) gives extreme photorealism/typography but heavy photoreal priors fight anime. Anime fine-tunes: **Chroma** (de-distilled FLUX.1 [schnell] derivative), **Kaleidoscope** (on 4 B FLUX.2 Klein) — drag the latent toward the anime manifold, combining FLUX anatomical coherence (fixing SDXL finger/limb mutations) with cel shading. **SD 3.5** also exists (MM-DiT, RF) but has not displaced SDXL for anime.

### 3.4 Architecture comparison

| Architecture | Params | Transport | Conditioning | Anime derivatives |
|---|---|---|---|---|
| SD 1.5 | 0.9 B | ε-pred (LDM) | tags | AnimateDiff base |
| SDXL | 2.6 B | ε-pred (LDM) | Danbooru tags | Animagine XL 4.0, Illustrious 2.0 |
| SDXL v-pred | 2.6 B | v-pred (LDM) | Danbooru tags | NoobAI-XL V-Pred |
| SDXL Pony | 2.6 B | ε-pred (LDM) | score tags | Pony Diffusion V6 XL |
| SDXL RF | 2.6 B | rectified flow (ODE) | Danbooru tags | ChenkinNoob-XL RF, Mugen |
| FLUX.1/2 | 4–12 B | rectified flow (MM-DiT) | natural language (T5XXL) | Chroma, Kaleidoscope |

---

## 4. Conditioning & Prompting

- **Danbooru-tag native (SDXL anime):** discrete classification — the tag `sword` activates the concept. Structured order + quality tags (§3.2). The native vocabulary for LoRA captions.
- **Score-tags (Pony):** the fixed `score_9,…` activation string (§3.2).
- **Natural-language (FLUX/T5XXL):** dense relational prose ("an anime character gripping a luminescent broadsword, blade emitting blue volumetric light"). Tag workflows do not transfer.
- **Token dilution (Illustrious):** front-load critical concepts in the 248-token window.
- **Captioning for training/conditioning:**
  - **WD14 / WD-v3 tagger** — multi-label classification over Danbooru taxonomy; produces booru tags (the SDXL native vocabulary).
  - **Florence-2** (Microsoft, ~1 GB VRAM; PromptGen v1.5/v2.0 via MiaoshouAI Tagger in ComfyUI) — autoregressive foundation VLM generating structured natural-language captions describing spatial position, lighting, anatomy; mathematically optimal to feed a T5XXL embedding for FLUX, and a sharper cross-attention gradient signal generally. Use WD14 for SDXL tag training, Florence-2 for FLUX/natural-language and caption augmentation.

---

## 5. Fine-Tuning

### 5.1 Technique hierarchy (anime characters, preference order)
1. **Standard LoRA** — `dim 16–32`, `alpha = dim` or `dim/2`. Best fidelity-per-effort; the default.
2. **LyCORIS LoCon** — `dim 16 / conv 8` — captures conv-layer **style** for style-bound characters.
3. **LyCORIS LoHa / LoKr** — very small datasets / style-transfer (Hadamard/Kronecker factorisations).
4. **DreamBooth full fine-tune** — ≥24 GB VRAM; a production "character checkpoint."
5. **Full-checkpoint fine-tune** — DeepSpeed ZeRO-2 on the 3090 Ti.
6. **Avoid pure Textual Inversion** for character fidelity — underperforms LoRA on anime.

### 5.2 Trainers & configuration
- **Trainer:** kohya_ss / sd-scripts (de-facto standard); OneTrainer alternative.
- **Optimiser:** AdamW (stable) or **Prodigy** (auto-LR, hands-off). **Precision:** bf16 (preferred) / fp16. **Scheduler:** cosine.
- **VRAM tricks:** gradient checkpointing (fits 1024² on 16 GB), cached latents, min-SNR-gamma loss weighting; **v-prediction + zero-terminal-SNR** when the base is v-pred.
- **SDXL dual-encoder:** train both text encoders (the project's `LoRATuner` auto-detects SDXL via `"xl"/"animagine"` in the model id and enables dual-encoder training; default base `OnomaAIResearch/Illustrious-XL-v2.0`). SDXL micro-conditioning: original_size / crop_top_left / target_size.
- **Per-GPU TOML presets:** e.g. `illustrious_character_4080_16gb.toml` (1024², batch 1, grad-checkpoint) and `noobai_vpred_3090ti_24gb.toml` (1024², batch 2–4, v-pred).

---

## 6. The End-to-End Character Pipeline (4K Video → Character LoRA)

The flagship capability — it reuses Image-Toolkit's FFmpeg extraction, similarity/dedup, and database.

| Stage | Operation | Tooling |
|---|---|---|
| 1 | **Frame extraction** | FFmpeg + **PySceneDetect**; scene-aware, deinterlaced, full-res; single-frame extraction at exact PTS (probe VFR; I-frame fast pass; scene-aware preferred pass). Reuses `video_frame_extractor.py`. |
| 2 | **Curation & dedup** | phash/SSIM dedup (reuse `SimilarityFinder`); drop blur/dupes; balance poses/expressions/lighting. |
| 3 | **Captioning** | WD14 tagger + Florence-2; trigger token + curated tag schema (consistent across the set). |
| 4 | **Augmentation** | mild flip/crop/colour-jitter (PyTorch); avoid over-augmentation that harms fidelity. |
| 5 | **LoRA fine-tune** | kohya_ss; §5 settings; per-GPU TOML. |
| 6 | **DreamBooth / full FT** (optional) | DreamBoothTuner; full checkpoint via DeepSpeed ZeRO-2 (3090 Ti). |
| 7 | **Diagnostics** | training hooks: loss/grad-norm curves, periodic validation-image sampling, intermediate-output monitoring, weight-norm visualisation. |
| 8 | **Inference** | ComfyUI/Forge; ControlNet pose, IP-Adapter reference; Real-ESRGAN anime_6B upscale. |
| 9 | **Video (optional)** | AnimateDiff motion module + the trained character LoRA; ToonCrafter inbetweening. |

---

## 7. Inference Frameworks, Samplers, VAE, Control

| UI | Strength | Role |
|---|---|---|
| **ComfyUI** | Graph-based, max control, best for video/ControlNet/multi-stage | **Primary** |
| **Forge / reForge** | Fast A1111-style iteration, low overhead | Secondary (fast single-image) |
| **A1111** | Mature extension ecosystem | Legacy / extensions |

- **Samplers (SDXL anime):** Euler a or **DPM++ 2M SDE Karras**; ~25–30 steps; **CFG 5–7** (lower for v-pred). For Pony/AnimateDiff: **DPM++ 2M** + automatic schedule, ~25 steps.
- **VAE:** SDXL **fp16-fix VAE** (avoids the black-image/NaN bug on flat regions).
- **Resolution:** 1024² base (1536² on Illustrious); hires-fix or tiled upscale to 1.5–2×.
- **Control:** **ControlNet** (OpenPose / depth / lineart / scribble) for pose & composition; **IP-Adapter** for character/style reference transfer; **regional prompting / latent couple** for multi-character scenes. TensorRT optimises ControlNet conditioning latency by ~40%.

---

## 8. Upscaling & Restoration

- **Real-ESRGAN anime_6B** (`RealESRGAN_x4plus_anime_6B`) — trained on anime degradation (JPEG blocks, cel-gradient loss, line thinning); preserves outlines where photo-SR over-smooths; built-in tile-and-stitch. 2× sharp / 4× blurry. **Shared with the ASP super-resolution stage** (`animation/super_res.py`).
- **4x-AnimeSharp** ESRGAN — alternative anime tiled upscaler.
- **APISR** — anime-production SR replicating multi-frame compression degradation (JPEG/WebP/AVIF/H.264-H.265 intra-prediction); inverts non-linear degradation while preserving 2-D topology (no photoreal hallucination in flat regions).
- **SUPIR / diffusion upscale** — detail-synthesising upscale when hallucinated detail is acceptable.

---

## 9. Video Generation — Temporal Injection Foundations

Training video from scratch is prohibitive; the dominant consumer-hardware paradigm **inserts temporal attention into a frozen spatial T2I network**, tricking an image generator into temporally-consistent sequences. The input latent `(B,C,H,W)` is reshaped to `(B,C,F,H,W)` to add the temporal axis `F`.

---

## 10. AnimateDiff

**Architecture.** A newly-initialised **motion module** (pseudo-3D temporal self-attention) is inserted after the spatial ResNet + cross-attention blocks of the SD U-Net. The **spatial layers are frozen** during motion training, preserving the base checkpoint's style/anatomy/composition priors; only the temporal layers learn generic motion (camera pans, object permanence) from large video datasets. At inference, any community checkpoint/LoRA/DreamBooth animates instantly without retraining — the framework is **model-agnostic**.

**Motion-module evolution:**

| Module | Base | Notes | Size |
|---|---|---|---|
| mm_sd_v14 | SD1.4/1.5 | initial; artifacts over long sequences | ~1.6 GB |
| mm_sd_v15 | SD1.5 | improved diversity/stability | ~1.6 GB |
| mm_sd_v15_v2 | SD1.5 | better kinematics; **Motion-LoRA compatible** (pan/zoom/tilt) | ~1.6 GB |
| v3_sd15_mm | SD1.5 | advanced stability; `sqrt_linear` beta | ~1.6 GB |
| mm_sdxl_v10_beta | SDXL | 1024² latent; needs linear beta + heavy VRAM opt | 950 MB |
| Hotshot-XL | SDXL | SOTA text-to-GIF alongside SDXL | ~1.0 GB |

**MotionLoRA:** extremely lightweight weights on the motion module to enforce specific camera dynamics (cinematic shots) cheaply.

**Anime fix (critical):** highly-tuned anime SDXL (Pony, Animagine) alter the latent/noise schedule; the standard AnimateDiff scheduler then mis-aligns temporal gradients → chaotic/pixelated output. **Force `beta_schedule = linear` (AnimateDiff-SDXL)** or autoselect; lock the empty-latent count to the model's context length (typically **16 frames**) to avoid batching errors.

---

## 11. Interpolation & Inbetweening

T2V from a blank latent is structurally unpredictable; V2V/interpolation ("inbetweening") is the production-aligned workflow.

### 11.1 AnimeInterp (correspondence-based)
Trained on **ATD-12K** (12 000 animation triplets). **Segment-Guided Matching** tracks piece-wise-coherent colour-segment outlines (not interior texture) to beat the flat-shading aperture problem; **Recurrent Flow Refinement** iteratively resolves large non-linear "teleportation" motion. **Limit:** optical-flow methods assume all target pixels exist in source frames — they fail on **dis-occlusion** (revealed hidden background) and extreme stylised deformation.

### 11.2 ToonCrafter (generative interpolation)
Adapts a pre-trained live-action image-to-video diffusion prior to cartoon interpolation. Inputs: start keyframe + end keyframe + optional sparse sketch → fluid inbetweens in ~20–24 s (DDIM-dependent). Three innovations:
1. **Toon Rectification Learning** — freeze temporal layers (preserve real-world physics/object permanence) while fine-tuning the **image-context projector + spatial layers** on curated cartoon data → eliminates "content leakage" (realistic pores/lighting on flat cels).
2. **Dual-Reference 3-D Decoder** — standard VAE compression destroys thin line art and bleeds flat colours in anime; this decoder injects uncompressed pixel data from the input keyframes as structural "supporting pillars" during decoding, preserving crisp detail.
3. **Sparse Sketch Guidance** — a frame-independent sketch encoder lets artists steer non-linear intermediate poses.

Dual-use: ToonCrafter is also the ASP **ghost-fill / occlusion-completion** model (`animation/anim_fill.py`).

### 11.3 ToonComposer & the DiT shift
**ToonComposer** (TencentARC) = "generative post-keyframing" — one DiT video model does **inbetweening + colourisation** simultaneously from one coloured keyframe + sparse uncoloured sketches (~70% manual-effort saving). Built on a **Video Diffusion Transformer (DiT)** that patchifies the latent video volume into tokens processed by self-attention (scales better than U-Nets, longer coherent context). **SLRA (Spatial Low-Rank Adapter):** in spatio-temporally *coupled* DiT attention, standard spatial-only LoRA is structurally impossible; SLRA adapts only spatial behaviour via two low-rank matrices applied before self-attention (residual added after), preserving the temporal prior — outperforming LoRA at comparable/lower parameter budget.

---

## 12. Foundation Video Models

- **Stable Video Diffusion (SVD)** — image-to-video; limited motion length/control; enhanced by conditioning tricks.
- **Wan2.1** — large foundation T2V/I2V; fine-tunable via **diffusion-pipe**; longer, more coherent clips than AnimateDiff at much higher VRAM (24 GB+ / offloading).
- **HunyuanVideo / CogVideoX class** — large DiT video models.
- **Audio/video-driven talking heads** — specialised lip-sync / pose-driven character animation architectures.

---

## 13. Video Control & Long-Sequence Inference

- **Consistency:** IP-Adapter (character/style across frames) + ControlNet (OpenPose/depth/lineart per frame).
- **Long clips:** **Prompt Travel** (scheduled prompt interpolation across frames), **Context Sliding / context windows** (overlapping temporal windows → arbitrarily long clips at fixed VRAM), spectral/latent modulation for flicker reduction.
- **VRAM strategy:** context windows + tiled VAE decode + fp8/GGUF motion models keep AnimateDiff-SDXL in 16 GB.

---

## 14. Hardware-Aware Deployment

### 14.1 Environment — the `uv` imperative
Use **uv** (Rust package manager) to unify interpreter/venv/dependency management (replaces pyenv+pip+conda), linking PyTorch to local CUDA without system-Python interference. E.g. `uv python install 3.10 && uv venv && uv pip install torch … --index-url …/cu124`.

### 14.2 RTX 3090 Ti (24 GB) — high-fidelity desktop
Runs the full 12 B FLUX.1 [dev] in native FP16/BF16 (~23.8 GB U-Net; T5 async-offload) — 20-step 1024² ≈ 12 s (~1.7 it/s). **TensorRT static compilation** (`ComfyUI_TensorRT`: Load Checkpoint → STATIC_TRT_MODEL_CONVERSION, fixed dims/batch) fuses attention into Tensor Cores → >3.0 it/s and −40% ControlNet latency. Full LoRA (1024² batch 2–4), DreamBooth, full-FT (ZeRO-2), Wan2.1, long AnimateDiff.

### 14.3 RTX 4080 mobile (12 GB) — constrained laptop
Native FLUX OOMs; quantisation is mandatory:

| Precision | VRAM | 20-step time | Fidelity loss | LoRA/ControlNet |
|---|---|---|---|---|
| Native FP16 | >24 GB | OOM | — | OOM |
| **FP8 (e4m3fn)** | ~11.6 GB | ~49–61 s | <1% | none (memory-bound) |
| **GGUF Q8_0** | ~11.0 GB | ~55 s | <2% | **excellent** |
| **GGUF Q4_0** | ~6.4 GB | ~35 s | ~10% | **exceptional** (headroom) |
| **BNB NF4 v2** | ~8.0 GB | ~47 s | ~8% | **broken** (LoRA-incompatible) |

**GGUF** (k-quant, per-matrix bit-depth) is SOTA for 12 GB: pair a Q4_0 U-Net with an FP8 T5XXL → ~8 GB total, leaving headroom for ControlNet/LoRA/FreeU. Launch `python main.py --lowvram --use-pytorch-cross-attention`. **Avoid NF4 if applying LoRAs** (early NF4 disrupts the attention blocks LoRA needs). The 16 GB desktop 4080 sits between: 1024² batch 1–2 + grad-checkpoint LoRA, FP8/GGUF FLUX, AnimateDiff with context windows.

---

## 15. Implementation Status in Image-Toolkit

- **Trainers:** `backend/src/models/lora_diffusion.py` (`LoRATuner`, SDXL dual-encoder, default Illustrious-XL-v2.0), `full_finetune.py` (DreamBooth/full FT), GAN/R3GAN wrappers.
- **Generation:** `sd3_wrapper.py` (`SD3Wrapper`, SD3.5; ControlNet TODO), `comfy_manager.py` + ComfyUI tab.
- **Data pipeline:** `backend/src/models/data/` — `video_frame_extractor.py`, `captioner.py`, `lora_dataset.py`, `augmentations.py`, `stitch_dataset.py`.
- **GUI tabs:** `gui/src/tabs/models/{gen,train}/` — LoRA train, SD3 gen, ComfyUI gen, GAN/R3GAN, diagnostics hooks (`models/hooks/`).
- **Gaps (→ `moon/roadmaps/content_generation.md`):** WD14/Florence-2 captioning, LyCORIS variants, v-pred/ztSNR support, IP-Adapter/ControlNet wiring, FLUX support, AnimateDiff/ToonCrafter video, the guided video→LoRA flow, per-GPU TOML presets, GGUF/FP8 quantised inference.

---

## Appendix A — Model & Tool Index

Bases: SD 1.5, SDXL; **Illustrious XL v1.1/2.0**, **NoobAI-XL** (eps/v-pred/RF), **Animagine XL 4.0**, **Pony Diffusion V6 XL**; **FLUX.1 [dev]/[schnell]**, **Chroma**, **Kaleidoscope** (FLUX.2 Klein), SD 3.5. Fine-tune: kohya_ss/sd-scripts, OneTrainer, LyCORIS (LoCon/LoHa/LoKr), DreamBooth, DeepSpeed ZeRO. Captioning: WD14/WD-v3, Florence-2 (PromptGen v1.5/2.0). Inference: ComfyUI, Forge/reForge, A1111; TensorRT; ComfyUI-GGUF, bitsandbytes. Control: ControlNet (OpenPose/depth/lineart/scribble), IP-Adapter, regional prompting/latent couple. Upscale: Real-ESRGAN anime_6B, 4x-AnimeSharp, APISR, SUPIR. Video: AnimateDiff (+MotionLoRA, Hotshot-XL), ToonCrafter, ToonComposer (DiT/SLRA), Wan2.1 (diffusion-pipe), SVD, HunyuanVideo/CogVideoX. Datasets: ATD-12K, AnimeRun, LinkTo-Anime, PaintBucket-Character. Env: uv.

## Appendix B — Quick Settings Cheat-Sheet

- **LoRA:** dim 16–32, alpha dim or dim/2; bf16; cosine; AdamW/Prodigy; grad-checkpoint; min-SNR-γ; v-pred+ztSNR if base is v-pred.
- **SDXL inference:** Euler a / DPM++ 2M SDE Karras; 25–30 steps; CFG 5–7; fp16-fix VAE; 1024² (1536² Illustrious).
- **Pony:** prepend `score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up`; DPM++ 2M; ~25 steps.
- **AnimateDiff-SDXL:** beta_schedule = linear; 16-frame context; motion module mm_sd_v15_v2 (SD1.5) / mm_sdxl_v10_beta or Hotshot-XL (SDXL).
- **FLUX on 12 GB:** GGUF Q4_0 U-Net + FP8 T5XXL (~8 GB); never NF4 with LoRAs.

## Appendix C — Source Reports Consolidated (now removable)

This document replaces: *Architectural Paradigms and Deployment Strategies for State-of-the-Art Anime Generative Models* (diffusion math, model architectures, Florence-2, deployment/quantisation, 4K→LoRA pipeline); *Anime Video Generation Deep Learning Research* (AnimateDiff, ToonCrafter, ToonComposer/DiT/SLRA, Wan2.1, SVD, ComfyUI video, MotionLoRA, prompt-travel/context-sliding); *Guide to Anime Image Generation: Models, LoRAs, and a Local Setup* (paid APIs, open models, character LoRAs, ComfyUI/A1111/Forge setup, ControlNet, upscaling); *Pipeline for Anime Diffusion Fine-Tuning on SDXL-Class Models* (FFmpeg/PySceneDetect extraction, dedup, augmentation, LoRA/DreamBooth/full-FT, DeepSpeed, diagnostics, inference); *Practitioner's Guide to State-of-the-Art Anime Image Generation and Custom-Character Fine-Tuning* (model landscape, fine-tuning comparison, VRAM, kohya_ss settings, end-to-end checklist).
