# ComfyUI Advanced Anime Wallpaper Pipeline
### Illustrious XL 2.0 — 7-Stage Architecture for 4K Desktop Wallpapers

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 0 · Style reference & aesthetic prior              [NEW] │
│  ┌──────────────────────┐     ┌──────────────────────────────┐  │
│  │   Style reference    │ ──► │   IP-Adapter + aesthetic     │  │
│  │  CLIP Vision encode  │     │  Strength 0.30 · 6.5 / 2.0  │  │
│  └──────────────────────┘     └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1 · Model stack & conditioning                           │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────┐  │
│  │  LoRA stack  │ ──► │  FreeU V2    │ ──► │ CLIP encode ×2 │  │
│  │  3 slots     │     │ b1 1.1·b2 1.2│     │  Dual pos/neg  │  │
│  └──────────────┘     └──────────────┘     └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2 · Base latent generation                               │
│  ┌──────────────────────┐     ┌──────────────────────────────┐  │
│  │    Empty latent      │ ──► │       Base KSampler          │  │
│  │  1344×768·native 16:9│     │  dpmpp_2m_sde · 30 steps    │  │
│  └──────────────────────┘     └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 3 · Dual-pass hires fix                       [UPGRADED] │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────┐  │
│  │NNLatentUpscale│ ──► │ Hires pass A │ ──► │  Hires pass B  │  │
│  │  Learned ×1.5│     │den.0.55·20 st│     │ den.0.30·12 st │  │
│  └──────────────┘     └──────────────┘     └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4 · Multi-target detailing                    [UPGRADED] │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────┐  │
│  │  VAE decode  │ ──► │ Face detailer │ ──► │ Hand detailer  │  │
│  │ Tiled·low    │     │YOLOv8·384px  │     │YOLOv8 person   │  │
│  │   VRAM       │     │guide size    │     │model           │  │
│  └──────────────┘     └──────────────┘     └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 5 · Pixel-space color grading                      [NEW] │
│  ┌──────────────────────┐     ┌──────────────────────────────┐  │
│  │  Image adjustments   │ ──► │    Film grain & sharpen      │  │
│  │  Sat, contrast,levels│     │  Unsharp mask + subtle grain │  │
│  └──────────────────────┘     └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 6 · Tiled super-resolution & export           [UPGRADED] │
│  ┌──────────────┐     ┌──────────────┐     ┌────────────────┐  │
│  │ Tiled ESRGAN │ ──► │Lanczos rescale│ ──► │ Save wallpaper │  │
│  │4×-AnimeSharp │     │ To 4K/1440p  │     │ PNG lossless   │  │
│  │   tile 512   │     │              │     │   output       │  │
│  └──────────────┘     └──────────────┘     └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

> **Architectural note on conditioning propagation.** The diagram shows a linear flow for clarity, but in the actual graph, Stage 1 outputs fan forward: the LoRA-patched model (post-FreeU) feeds the KSamplers in Stages 2 and 3 *and* the detailers in Stage 4. The CLIP conditioning feeds all four of those nodes. Stage 0's IP-Adapter output merges into Stage 2's positive conditioning only.

---

## What Changed vs the Original Pipeline

| Stage | Status | Key Change |
|---|---|---|
| Stage 0 | **NEW** | IP-Adapter style reference + SDXL aesthetic score conditioning |
| Stage 1 | Upgraded | LoRA stack expanded to 3 chained slots |
| Stage 2 | Upgraded | Sampler changed from `dpmpp_2m` to `dpmpp_2m_sde` |
| Stage 3 | **Upgraded** | `NNLatentUpscale` replaces bicubic; second low-denoise pass added |
| Stage 4 | **Upgraded** | Hand/body detailer added; VAE decode becomes tiled |
| Stage 5 | **NEW** | Pixel-space color grading before ESRGAN |
| Stage 6 | Upgraded | ESRGAN becomes tiled; VRAM-safe at any resolution |

---

## Stage 0 — Style Reference & Aesthetic Prior

This stage is optional but strongly recommended when you want a consistent aesthetic across a wallpaper series (e.g., always a warm painterly look, or always a cold cel-shaded palette).

### CLIP Vision → IP-Adapter

Load a reference image — a painting, a screenshot from a series with the right art style, or a manually curated wallpaper. Use the `CLIPVisionEncode` node and connect it to `IPAdapterAdvanced` (from the `ComfyUI_IPAdapter_plus` extension).

| Parameter | Value | Notes |
|---|---|---|
| `strength` | `0.25–0.40` | Above `0.45` suppresses character LoRAs; below `0.20` is imperceptible |
| `weight_type` | `style transfer precise` | Applies style conditioning uniformly across attention layers |
| `combine_embeds` | `average` | Use `concat` only if using multiple style references |

### SDXL Aesthetic Score Conditioning

Illustrious XL inherits SDXL's extra conditioning input that accepts two floating-point aesthetic score values.

| Parameter | Value | Notes |
|---|---|---|
| `aesthetic_score` (positive) | `6.5` | Range `6.0–7.5`; above `8.0` produces over-processed outputs |
| `aesthetic_score` (negative) | `2.0` | Keep below `3.0` to suppress low-resolution artifacts |
| `crop_coords_top_left` | `(0, 0)` | Standard SDXL extra conditioning |

---

## Stage 1 — Model Stack & Conditioning

### Checkpoint

```
illustriousXL20_v20.safetensors
```

### LoRA Stack

Use `LoraLoaderModelAndCLIP` chained three times, or the `LoraLoaderStack` node from `comfyui-prompt-control`. Slot ordering matters — earlier slots have higher semantic priority.

| Slot | Purpose | Example | Strength Range |
|---|---|---|---|
| 1 | Character LoRA | `JN_Hisato_Azuma_Illus.safetensors` | `0.80–0.90` |
| 2 | Style LoRA | `soft_painterly_v2.safetensors` | `0.50–0.65` |
| 3 | Detail LoRA | `hair_fabric_detail_xl.safetensors` | `0.30–0.45` |

**When to adjust:** Reduce character LoRA below `0.75` if anatomy deforms. Reduce style LoRA if colors look artificially pastel. Reduce detail LoRA if you see texture noise bleeding into backgrounds.

### FreeU V2

Place between the model output and all KSampler model inputs. The `b` values amplify backbone skip connections for structural coherence; the `s` values attenuate detail skip connections to prevent high-frequency noise.

| Parameter | Value | Adjustment |
|---|---|---|
| `b1` | `1.1` | Increase toward `1.2` for stronger structural coherence |
| `b2` | `1.2` | Decrease toward `1.1` if you see structural ringing |
| `s1` | `0.9` | Increase toward `0.95` if outputs look soft/blurry |
| `s2` | `0.2` | Rarely needs adjustment |

### CLIP Text Encode (Positive)

Use attention weighting with the `(keyword:weight)` syntax:

```
masterpiece, best quality, ultra-detailed, 1girl, solo, hisato_azuma,
[character attire], (dynamic angle:1.15), (wide shot:1.2),
breathtaking fantasy landscape, vibrant colors, ray tracing,
cinematic lighting, depth of field
```

**Weight guidelines:** Structural composition keywords (`dynamic angle`, `wide shot`) at `1.1–1.2`. Character LoRA trigger tokens at `1.0` (default). Never exceed `1.4` on any single token — this triggers attention collapse.

### CLIP Text Encode (Negative)

```
lowres, bad anatomy, bad hands, text, error, missing fingers,
extra digit, fewer digits, cropped, worst quality, low quality,
normal quality, jpeg artifacts, signature, watermark, username,
blurry, artist name, 3d, realistic
```

---

## Stage 2 — Base Latent Generation

### Empty Latent Image

| Parameter | Value | Notes |
|---|---|---|
| `width` | `1344` | Native SDXL training distribution |
| `height` | `768` | Exactly 16:9 at native resolution |
| `batch_size` | `1` | Increase for batch runs; VRAM scales linearly |

### Base KSampler

| Parameter | Value | Range | Notes |
|---|---|---|---|
| `sampler_name` | `dpmpp_2m_sde` | — | SDE variant prevents color-blob premature convergence |
| `scheduler` | `karras` | `karras` or `exponential` | Use `exponential` if backgrounds have over-smooth gradients |
| `steps` | `30` | `28–32` | Below `25` produces structural artifacts in wide shots |
| `cfg` | `6.5` | `5.5–7.0` | Above `7.5` over-saturates skies and blows highlights |
| `denoise` | `1.0` | — | Full denoise for base generation |
| `seed` | randomize | — | — |

**High CFG mitigation:** If you need CFG above `7.5`, add the `ModelSamplingDiscrete` node with `zsnr=true` (zero-SNR rescaling) to the model chain. This allows higher CFG without the saturation artefacts.

---

## Stage 3 — Dual-Pass Hires Fix

The original pipeline used a single bicubic latent upscale. Bicubic is a mathematical interpolation with no semantic understanding — it introduces ringing at sharp edges (hair outlines, outfit borders) and cannot hallucinate new structural detail.

### NNLatentUpscale

This node runs a small trained neural network on the latent tensor. It preserves color histograms, attention-region centroids, and major structural lines far better than bicubic.

| Parameter | Value |
|---|---|
| `upscale_method` | `NNLatentUpscale` |
| `scale_factor` | `1.5` |
| Input resolution | `1344×768` |
| Output resolution | `2016×1152` |

### Hires Pass A — Structural Injection

| Parameter | Value | Range | Notes |
|---|---|---|---|
| `sampler_name` | `dpmpp_2m_sde` | — | Same SDE variant as base |
| `scheduler` | `karras` | — | — |
| `steps` | `20` | `18–22` | — |
| `cfg` | `6.0` | `5.5–6.5` | — |
| `denoise` | `0.55` | `0.50–0.58` | Lower if composition drifts; raise if output lacks detail |

**When to adjust denoise A:** If the character repositions or background elements appear/disappear, drop toward `0.45`. If the image looks almost identical to the base output with no added detail, push toward `0.60`.

### Hires Pass B — Polishing

| Parameter | Value | Range | Notes |
|---|---|---|---|
| `sampler_name` | `euler` or `dpmpp_2m` | — | Deterministic; no SDE noise for final polish |
| `scheduler` | `normal` | — | — |
| `steps` | `12` | `10–15` | — |
| `cfg` | `6.0` | — | — |
| `denoise` | `0.30` | `0.25–0.32` | Cleans aliasing from Pass A without altering structure |

This is where fabric textures, hair strand definition, and background gradient banding get cleaned up.

---

## Stage 4 — Multi-Target Detailing

### VAE Decode (Tiled)

Use `VAEDecodeTiled` rather than `VAEDecode`. At `2016×1152`, standard VAE decode requires ~10 GB VRAM; tiled decode keeps peak usage under 6 GB.

| Parameter | Value |
|---|---|
| `tile_size` | `512` |
| `stride` (overlap) | `256` |

### Face Detailer

| Parameter | Value | Range | Notes |
|---|---|---|---|
| `bbox_detector` | `face_yolov8m.pt` | — | The `m` (medium) variant; `n` (nano) misses small faces in wide shots |
| `guide_size` | `384` | — | — |
| `max_size` | `1024` | — | — |
| `denoise` | `0.34` | `0.30–0.38` | — |
| `sampler_name` | `euler` | — | Stable/predictable; required for precise mask compositing |
| `scheduler` | `normal` | — | — |
| `steps` | `20` | — | — |
| `cfg` | `5.0` | — | — |
| `bbox_threshold` | `0.50` | `0.45–0.60` | Lower = more detections including false positives |

### Hand / Body Detailer

This is the most impactful new addition. Anime hands in wide landscape wallpapers are a consistent failure mode — wrong finger counts, fused digits, impossible poses.

| Parameter | Value | Range | Notes |
|---|---|---|---|
| `bbox_detector` | `hand_yolov8s.pt` | — | Or `person_yolov8m-seg.pt` for full-body correction |
| `guide_size` | `256` | — | Hands are smaller than faces in wide compositions |
| `denoise` | `0.27` | `0.25–0.30` | Lower than face detailer — correct topology, don't regenerate |
| `sampler_name` | `euler` | — | — |
| `steps` | `15` | — | — |

> **Important:** Run face detailer first. Feed its composited output as input to the hand detailer. If using `person_yolov8m-seg.pt` for full-body, limit the active mask to the intersection of the segmentation and a lower-body bounding box — otherwise it may redraw the face a second time.

---

## Stage 5 — Pixel-Space Color Grading

After the detailers, the image can exhibit two subtle artifacts: (1) a slight luminance shift where the YOLO-masked region has a different gamma than the surrounding image, and (2) the overall image can look slightly desaturated compared to what the SDXL latent "intended" before VAE decode. Correcting these before ESRGAN is critical — the GAN will amplify whatever tonal characteristics it receives.

### Image Adjustments Node

| Parameter | Value | Range | Notes |
|---|---|---|---|
| `saturation` | `+0.10` | `+0.08–+0.15` | VAE decode is systematically slightly desaturating |
| `contrast` | `+0.07` | `+0.05–+0.10` | Gentle lift only |
| `brightness` | `+0.02` | `0–+0.05` | Only if outputs are consistently dark; avoid if not needed |
| `hue` | `0` | — | Never adjust; IXL's color relationships are internally consistent |

### Unsharp Mask

Apply *before* film grain — grain on a blurry image looks wrong; grain on a sharp image looks intentional.

| Parameter | Value |
|---|---|
| `radius` | `2.0` |
| `strength` | `0.45–0.55` |
| `threshold` | `10` |

### Film Grain

Add with `AddNoise` or `ImageFilterNode`. Apply grain at this stage, *before* ESRGAN — grain added after the 4× upscale will look blocky since pixel-level noise scales up with the image.

| Parameter | Value |
|---|---|
| `sigma` (normalized) | `0.02–0.04` |
| `noise type` | `gaussian` |

---

## Stage 6 — Tiled Super-Resolution & Export

### Why Tiled ESRGAN

At `2016×1152` input, a 4× ESRGAN produces an `8064×4608` tensor. Without tiling, this requires holding the entire image in VRAM (14–20 GB). The `ImageUpscaleWithModel` node supports tiled inference via the `tile_size` parameter.

| Parameter | Value | Notes |
|---|---|---|
| `tile_size` | `512` | Use `768` on slow GPUs to reduce overhead at some memory cost |
| `overlap` | `32` | Prevents visible tile seams via edge blending |

### ESRGAN Model Selection

| Model | Best For |
|---|---|
| `4x-AnimeSharp` | **Recommended.** Trained on clean line art and flat color regions |
| `4x_foolhardy_Remacri` | Good middle ground if AnimeSharp over-sharpens thin outlines |
| `4x_NMKD-Siax_200k` | Not recommended for anime; adds photo-realistic grain that clashes with the aesthetic |

### Lanczos Rescale to Target

The ESRGAN output (`8064×4608`) exceeds standard 4K because the 4× scale from a native 16:9 latent doesn't land exactly on standard monitor dimensions.

| Parameter | Value |
|---|---|
| `upscale_method` | `lanczos` |
| `crop` | `disabled` |
| `width` (4K) | `3840` |
| `height` (4K) | `2160` |
| `width` (1440p) | `2560` |
| `height` (1440p) | `1440` |

**Why Lanczos:** Mathematically correct for this downsampling ratio — smooth, anti-aliased reduction with good frequency preservation. Do not use area or bilinear downsampling; they introduce more blurring than Lanczos at this scale factor.

### Save Image

| Parameter | Value |
|---|---|
| `filename_prefix` | `wallpaper_[seed]_[steps]` (recommended for tracking) |
| `file format` | `PNG` (lossless) |

---

## Quick Reference: Parameter Decision Table

| Symptom | Stage | Adjustment |
|---|---|---|
| Character anatomy deforms | Stage 1 | Reduce character LoRA strength below `0.75` |
| Colors look artificially pastel | Stage 1 | Reduce style LoRA strength below `0.55` |
| Output looks soft/blurry overall | Stage 1 | Increase FreeU `s1` toward `0.95` |
| Structural ringing at edges | Stage 1 | Decrease FreeU `b2` toward `1.1` |
| Over-saturated skies, blown highlights | Stage 2 | Reduce CFG below `6.5`; or enable `zsnr=true` |
| Composition drifts in hires fix | Stage 3 | Lower Pass A denoise toward `0.45` |
| Hires output too similar to base | Stage 3 | Raise Pass A denoise toward `0.60` |
| Remaining background aliasing | Stage 3 | Raise Pass B denoise toward `0.32` |
| Wrong finger counts in output | Stage 4 | Enable hand detailer; lower denoise if hands are overdrawn |
| Luminance seam around face | Stage 4 | Lower face detailer denoise toward `0.28` |
| Output looks flat/desaturated | Stage 5 | Increase saturation adjustment toward `+0.15` |
| ESRGAN out of VRAM | Stage 6 | Reduce `tile_size` to `512`; ensure `overlap=32` |
| Visible tile seams in 4K output | Stage 6 | Increase `overlap` to `48–64` |
| ESRGAN over-sharpens thin lines | Stage 6 | Switch to `4x_foolhardy_Remacri` model |

---

*Pipeline architecture: 7 stages · Base resolution: 1344×768 · Final output: 3840×2160 (4K) or 2560×1440 (1440p)*
