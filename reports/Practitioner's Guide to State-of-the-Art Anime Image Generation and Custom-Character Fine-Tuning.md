# A 2025 Practitioner's Guide to State-of-the-Art Anime Image Generation and Custom-Character Fine-Tuning on RTX 4080 (16 GB) and RTX 3090 Ti (24 GB)

## TL;DR
- For the strongest combination of out-of-the-box anime quality, character knowledge, fine-tunability, and consumer-GPU friendliness in 2025, build your stack around **Illustrious XL v1.1 / v2.0** (or its derivative **NoobAI-XL v-pred 1.0**) as the SDXL-class base model, train **rank-16–32 LoRAs** (or LyCORIS LoCon for style-heavy characters) with **kohya_ss / sd-scripts**, and run inference in **ComfyUI** (with **Forge/reForge** as a secondary UI for fast iteration). Both GPUs comfortably handle 1024–1536 px SDXL inference and LoRA training; the 3090 Ti can train LoRAs at full 1024² + batch 2–4, while the 4080 laptop trains at 1024² batch 1–2 with gradient checkpointing.
- **Flux.1-dev** is the current quality king for prompt adherence/photoreal but is a poor primary anime base in 2025: VRAM-heavy (needs FP8 or GGUF Q8 to fit comfortably on 16 GB), slow to train (~18 s/it at 1024² on a 3090-class card per Civitai data), and its anime ecosystem (LoRAs, ControlNets, character knowledge) is a tiny fraction of the SDXL/Illustrious community. Use it only as a *secondary* model for stylized realism or when you need superior text rendering.
- Fine-tuning hierarchy for anime characters (in order of practical preference): **Standard LoRA (dim 16–32, alpha = dim or dim/2)** → **LyCORIS LoCon (dim 16/conv 8)** for characters tied to a specific art style → **LyCORIS LoHa/LoKr** for very small datasets or style-transfer scenarios → **DreamBooth full fine-tune** only when you have ≥24 GB VRAM and need a "character checkpoint" for production. Avoid pure Textual Inversion for character fidelity — it underperforms LoRA on anime characters.

---

## Key Findings

### 1. Model landscape (anime, SDXL-era and beyond)
- **Illustrious XL** (OnomaAI) is the de-facto anime base model of late 2024/2025. v1.0 trains natively at 1536², v1.1 adds natural-language captioning, v2.0 (early 2025) is explicitly tuned for *fine-tune stability* and supports 512–1536 px with 1:10 aspect ratio bucketing. It encodes thousands of Danbooru artists/characters and is the upstream base for almost every popular 2025 anime checkpoint (WAI-Illustrious, Hassaku XL Illustrious, Diving-Illustrious-Anime, Plant Milk, Obsession, etc.).
- **NoobAI-XL** (Laxhar Lab) is a heavy fine-tune of Illustrious-xl-early-release-v0 on the full Danbooru + e621 corpus (~12.7–13 M images). Two prediction objectives ship: an *epsilon* version (drop-in like SDXL) and a *v-prediction* 1.0 version with stronger color/lighting fidelity. V-pred requires Euler/DDIM samplers (Karras schedules unsupported), CFG 4–5, 28–35 steps, and "Zero Terminal SNR" enabled in the UI; ComfyUI, reForge, Forge dev, and A1111 dev branch all support it.
- **Pony Diffusion V6 XL** is still SDXL-based (~2.6 B params, 2.6 M training images) and uses the score_9/score_8_up booru-prefix prompting paradigm. Its huge LoRA ecosystem makes it the second most-supported 2025 anime stack. **Pony V7** (released Nov 2025 per ponydiffusion.com / Apatero) is a complete architectural break — it abandons SDXL for **AuraFlow (~7 B params, 10 M training images)** with a more balanced 25 % anime / 25 % realism / 20 % western cartoon mix, "style grouping" for super-artist clustering, and *no LoRA backwards-compatibility* with V6. V7 is reported to need 12 GB minimum, 16 GB comfortable, 24 GB recommended; the V7-family LoRA tooling is still maturing as of early 2026.
- **Animagine XL 4.0 / 4.0-Opt** (Cagliostro Lab, Jan–Feb 2025) is a from-scratch SDXL retrain on 8.4 M anime images (~2 650 GPU-hours). Tag-ordered prompts, knowledge cutoff 2025-01-07, recommended Euler-Ancestral, CFG 5–7, 25–28 steps. It is excellent for clean general-purpose anime but has a smaller character roster than NoobAI.
- **Flux.1-dev** (Black Forest Labs, 12 B-param DiT) gives the best text rendering and prompt adherence but its anime knowledge is shallow and the LoRA ecosystem is thin. Flux community anime LoRAs (modern-anime-lora, FAS-v2, etc.) work but are clearly a step below Illustrious/NoobAI for "true" anime aesthetics. SD3/SD3.5 is essentially absent from the 2025 anime conversation due to its license and the community's strong preference for Illustrious-family checkpoints.
- **SD 1.5 anime models** (NAI, AnyLoRA, Counterfeit, MeinaMix, AOM3) are now legacy. They retain value only for very low-VRAM (≤6 GB) setups and for porting old LoRAs; both your GPUs vastly exceed their requirements.

**Bottom-line model selection.** For *primary* anime work choose one of:
1. **Illustrious XL v1.1 or v2.0-stable** (best fine-tune base, broadest LoRA compat).
2. **NoobAI-XL Epsilon 1.1 or V-Pred 1.0** (best raw aesthetic/character knowledge; pick V-pred if you can use Euler + zero-terminal-SNR).
3. **Animagine XL 4.0-Opt** (cleanest "default" anime, excellent for portraits).
4. **Pony V6 XL** (if you depend on existing Pony LoRAs or score_X prompting).

Keep a **Flux.1-dev FP8 or GGUF Q8** install as a secondary model for text-in-image, semi-realistic anime, and rare prompts where SDXL fails.

### 2. Fine-tuning techniques compared

| Method | Typical file size (SDXL) | VRAM (1024² training) | Best for | Caveats |
|---|---|---|---|---|
| **Textual Inversion** | <1 MB | ~8 GB | Adding a *style* concept handle to an already-knowledgeable model | Weak for character identity/anatomy; anime communities have largely abandoned it for characters |
| **LoRA (standard, "LierLa")** | 50–200 MB (dim 8–32) | 10–14 GB w/ grad-ckpt | **Anime characters** (default choice) | Linear-only; can struggle to capture extreme styles |
| **LyCORIS LoCon** | 25–200 MB | ~12–14 GB | Character + tied art style | Slightly more rigid than LoRA; oldest LyCORIS variant |
| **LyCORIS LoHa** | ~30 MB (dim 8/4) | 13–16 GB | Style transfer and combining style + character; small datasets | Can NaN at high rank; more brittle for complex characters |
| **LyCORIS LoKr** | ~2.5 MB | 13–16 GB | Tiny files for simple characters; on-device deployment | Poor cross-checkpoint portability |
| **DoRA** | ~LoRA | ~LoRA + 5–10 % | Better detail retention vs LoRA at same rank | Higher VRAM; some inference tools still patchy |
| **DreamBooth full fine-tune** | 6–7 GB checkpoint | 24 GB+ for SDXL | Production "character checkpoint", maximum fidelity | Loss of generalization without regularization images; only viable on the 3090 Ti |

For an *anime character*, the empirically dominant 2025 recipe is a **standard LoRA, dim/rank 16–32, alpha = dim or dim/2**, trained for 1 200–2 400 effective steps. Civitai community guides converge on dim 16–32 / alpha 16 for characters; dim 64+/alpha 32 only when you also need to capture multiple costumes or a tied art style.

### 3. Architecture / VRAM at a glance (your two GPUs)

| Model family | Inference VRAM | LoRA train VRAM (1024², dim 32) | Native res |
|---|---|---|---|
| SD 1.5 anime | 4–6 GB | 6–8 GB | 512 |
| SDXL / Illustrious / NoobAI / Pony V6 / Animagine 4 | 8–12 GB | 12–18 GB (grad-ckpt mandatory at <16 GB) | 1024 (Illustrious up to 1536) |
| Pony V7 (AuraFlow 7 B) | 12–16 GB | 20–24 GB+ | 1024 |
| Flux.1-dev FP16 | 22–24 GB | 24 GB+ (block-swap) | 1024 |
| Flux.1-dev FP8 / GGUF Q8 | 11–14 GB | 16–20 GB w/ Quanto int8 + grad-ckpt | 1024 |

**Both your GPUs can do everything in this table except (a) Flux FP16 inference on the 4080 and (b) full-precision Flux training without aggressive optimization.** The 24 GB 3090 Ti is the more flexible workhorse — it can do batch-2 SDXL LoRA at 1024² without grad-ckpt, batch-1 Flux LoRA at 1024² with int8 quanto (per SimpleTuner data), and full SDXL DreamBooth. The laptop 4080 (16 GB) is closer to the practical *minimum* for comfortable SDXL LoRA training: gradient checkpointing on, batch 1–2, AdamW8bit or Adafactor.

### 4. Inference framework comparison (2025 state)

- **ComfyUI** — Now the de-facto power-user UI. Fastest by ~2× over A1111 in batch tests; first-class support for new architectures (Flux, NoobAI v-pred, Pony V7/AuraFlow); node-based workflows trivially shareable as JSON; native fp8/GGUF/SageAttention integration. *Recommended primary UI.*
- **Forge / reForge** (lllyasviel + community) — A1111-compatible fork with much better VRAM use and built-in v-prediction/zero-SNR support; the most popular UI for NoobAI-XL V-pred among the Civitai community. *Recommended secondary UI for fast prototyping and ADetailer-based portrait workflows.*
- **AUTOMATIC1111 (A1111) main** — Largest extension ecosystem but slower; v-pred only on dev branch; falling behind Forge for SDXL anime work.
- **InvokeAI** — Best canvas/inpainting UX but more conservative on bleeding-edge models and historically NSFW-restrictive defaults; smaller anime community footprint.
- **Fooocus** — Midjourney-style "easy mode"; SDXL-only, no Flux/Pony-V7 support, limited LoRA flexibility — not appropriate for a research workflow.

### 5. 2024-2025 memory/speed techniques relevant to your GPUs
- **SageAttention** (Patch Sage Attention KJ node in ComfyUI): 25–30 % speedup on SDXL on a 3090; FP16 modes work on Ampere; FP8 mode is **Ada/Hopper-only** so the 3090 Ti will crash on FP8 SageAttention but works fine with FP16 cuda/triton. The laptop 4080 (Ada) supports all SageAttention modes including FP8.
- **xFormers / PyTorch SDPA / Flash-Attention 2** — Default acceleration; Flash-Attn 2 wheels exist for both Ampere and Ada.
- **fp8 / bf16 mixed precision** — Native bf16 on RTX 30/40 series. Ada (4080) has fp8 tensor cores; Ampere (3090 Ti) does *not* — fp8 quantized weights still load on a 3090 but compute falls back to bf16/fp16, giving VRAM savings without speedups. Important caveat: do not naively quantize *during training* on a 3090.
- **GGUF (Q8_0, Q6_K, Q4_K_S/M, Q3, Q2)** — Primary route for fitting Flux on 16 GB. Q8_0 is essentially indistinguishable from FP16 for anime; Q4_K_M is the practical floor for quality; Q2/Q3 noticeably degrade. Use **city96/FLUX.1-dev-gguf** with the GGUF loader nodes in ComfyUI.
- **block-swap (kohya sd3-flux branch)** — Trades RAM for VRAM during training; allows Flux LoRA at 1024² on 12–16 GB by swapping transformer blocks to CPU.
- **`--cache_latents`, `--cache_text_encoder_outputs`, `--gradient_checkpointing`, `--full_bf16`, `--no_half_vae`, `--mixed_precision=bf16`, `--xformers`** — The standard kohya cocktail; combined they cut SDXL training VRAM by ~40 % at the cost of ~17–22 % training speed (Puget Systems benchmark).
- **AdamW8bit (bitsandbytes) / Adafactor / Prodigy / CAME** — On a 16 GB card use AdamW8bit (saves ~25–30 % optimizer-state VRAM) or Adafactor (lowest VRAM, slightly noisier convergence). Prodigy is the go-to for "set-and-forget" LR (always set LR=1.0 with Prodigy).

### 6. Recommended end-to-end pipeline (anime character LoRA)

The dominant 2025 recipe in the Civitai/HoloStrawberry/Linaqruf communities for an Illustrious or Pony character LoRA:

1. **Curate 20–80 images** (Civitai community sweet spot: 25–50 for a single character, 60–120 if multiple costumes). Use diverse poses, expressions, framings; avoid duplicates, watermarks, low-res (<512²) and AI-generated images. Crop loosely; SDXL bucketing handles aspect ratios up to 1:10.
2. **Auto-tag with WD14** (`SmilingWolf/wd-swinv2-tagger-v3` or `wd-vit-tagger-v3` via `tag_images_by_wd14_tagger.py --onnx --remove_underscore --character_tag_expand --character_tags_first --always_first_tags "1girl"`). Threshold ~0.35; raise character threshold to 0.7 to keep only confident character tags.
3. **Edit captions** in a tag editor (A1111's Dataset Tag Editor extension, BooruDatasetTagManager, or kohya GUI's manual captioning). Critical step: **prune the tags that describe the character's *intrinsic* features** (hair color, eye color, fixed clothing) so the model bakes those into the trigger word, while *keeping* tags for variable attributes (pose, expression, background, lighting).
4. **Insert a unique trigger token** at the start of every caption (e.g., `mychar_xyz, 1girl, smiling, ...`).
5. **(Optional) Regularization images**: 100–500 generic anime images of `1girl`/`1boy` from the same base model — only meaningful for DreamBooth, not strictly needed for LoRA.
6. **Train** with kohya_ss (settings table below).
7. **Validate** with sample prompts every epoch; pick the epoch where character likeness first stabilizes without artifact bleed (usually epoch 6–12 of 10–20).
8. **Inference** in ComfyUI/Forge with the chosen base model, LoRA strength 0.7–1.0, ADetailer (`face_yolov8n.pt` for SDXL anime faces, or `Adetailer Face finder` for non-realistic) and optional 1.5–2× hi-res fix with 4x-UltraSharp or NMKD-Siax.

---

## Details

### A. Recommended software stack (step-by-step)

**Operating system note.** On Linux (Ubuntu 22.04/24.04) PyTorch + bitsandbytes + xformers + Flash-Attn 2 builds are smoother and ~5–10 % faster on the 3090 Ti than Windows. On the laptop 4080, Windows is fine if you stick to the Forge + ComfyUI portable + kohya_ss zip stack; otherwise WSL2 + CUDA toolkit gives Linux-grade performance.

**Common prerequisites (both machines):**
- NVIDIA driver ≥ 555 (for CUDA 12.4+/12.6) — required for current PyTorch 2.4–2.7, SageAttention 2.x, Flash-Attn 2.7.
- CUDA 12.4 toolkit (or 12.6/12.8 if you want CUDA 13/PyTorch 2.7).
- Python 3.10.x (kohya_ss is most stable here; Python 3.11/3.12 work for ComfyUI but break older bitsandbytes wheels).
- Git, MS Build Tools / `build-essential`, MS Visual C++ 2015–2022 redistributable on Windows.
- 50–100 GB free disk for base models (Illustrious, NoobAI eps + v-pred, Animagine 4, Pony V6, Flux dev FP8 / Q8 GGUF, t5xxl_fp8/Q8, clip_l, ae.safetensors).

**Step-by-step install**
1. **ComfyUI**: `git clone https://github.com/comfyanonymous/ComfyUI && cd ComfyUI && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt` (use the Windows portable build on Windows). Add **ComfyUI-Manager**, **ComfyUI-KJNodes** (provides Patch Sage Attention KJ node), **ComfyUI-Custom-Scripts**, **ComfyUI-Impact-Pack** (for Face Detailer), **ComfyUI-GGUF** (city96), and **rgthree-comfy**.
2. **Forge / reForge**: `git clone https://github.com/lllyasviel/stable-diffusion-webui-forge` (or the reForge fork). Run `webui-user.bat`/`.sh`. Forge is the most ergonomic UI for NoobAI v-pred; enable *Zero Terminal SNR* in Settings → Sampler parameters.
3. **kohya_ss GUI** (training): on Windows `git clone https://github.com/bmaltais/kohya_ss && cd kohya_ss && setup.bat` and pick option 1 (install GUI), then optionally option 2 (CUDNN 8.9). On Linux: `./setup.sh`. Run `accelerate config` once: `This machine` → `No distributed training` → no CPU-only → no torch dynamo → no DeepSpeed → bf16 mixed precision. Launch with `gui.bat --listen 127.0.0.1 --server_port 7860`.
4. **SageAttention** (optional, big speedup on Ada; Flash-Attention-equivalent on Ampere):
   - Windows portable ComfyUI: `python_embeded\python.exe -m pip install triton-windows sageattention` then add `--use-sage-attention` to the launcher. If pip fails, grab a prebuilt wheel from the woct0rdho repo matching your CUDA/Torch/Python triple.
   - Linux: `pip install triton sageattention`.
   - Verify with the `Patch Sage Attention KJ` node placed right after the CheckpointLoader in your workflow; on a 3090 Ti use `auto` or `triton` precision (FP8 will crash); on the Ada 4080 you can try fp8 mode for further gains.
5. **bitsandbytes** (for AdamW8bit during LoRA training):
   - Linux: `pip install bitsandbytes` (CUDA 12.x wheels native).
   - Windows: kohya_ss bundles a prebuilt; if it errors, install the `bitsandbytes-windows` fork.
6. **Models**: download to `ComfyUI/models/checkpoints` and symlink into `kohya_ss` and Forge:
   - `Illustrious-XL-v2.0-stable.safetensors` (or v1.1)
   - `noobaiXLNAIXL_vPred10Version.safetensors` (and the epsilon 1.1 version)
   - `animagineXL40_v40Opt.safetensors`
   - `ponyDiffusionV6XL.safetensors`
   - **For Flux**: `flux1-dev-fp8.safetensors` *or* `flux1-dev-Q8_0.gguf` + `t5xxl_fp8_e4m3fn.safetensors` + `clip_l.safetensors` + `ae.safetensors`.
   - WD14 tagger model auto-downloads on first run.
7. **VAEs**: SDXL anime models bundle their own VAE (sdxl_vae or fixed-fp16 variants). The Flux `ae.safetensors` is mandatory for any Flux workflow.

### B. Dataset preparation in detail

**Directory layout (kohya_ss "training folder" convention):**
```
project/
├── img/
│   └── 10_mychar 1girl/        # "<repeats>_<class prompt>"; 10 repeats per epoch
│       ├── 0001.png
│       ├── 0001.txt            # WD14 caption
│       └── ...
├── reg/                        # optional regularization images (DreamBooth only)
│   └── 1_1girl/
└── output/
```
The `10_` prefix is the **per-image repeat count per epoch**. With 30 images × 10 repeats = 300 steps/epoch at batch 1, ×10 epochs = 3 000 steps; at batch 4 → 750 *update* steps. Common community settings: anime characters use repeat=8–10, ~10–20 epochs; styles use repeat=3–5, ~20–40 epochs.

**WD14 tagging command (kohya finetune dir):**
```bash
python finetune/tag_images_by_wd14_tagger.py \
  --onnx --repo_id SmilingWolf/wd-swinv2-tagger-v3 \
  --batch_size 4 --thresh 0.35 \
  --remove_underscore --character_tag_expand \
  --character_tags_first --always_first_tags "1girl" \
  --caption_extension .txt \
  ./img/10_mychar
```
Then run the optional `make_captions.py` (BLIP) only if you want a natural-language sentence appended (Animagine 4, Illustrious 2 like a hybrid; pure NoobAI/Pony prefer pure tags).

**Caption-pruning rules for character LoRAs.**
1. *Add* a unique trigger token first: `mychar_xyz`.
2. *Keep* general/scene/pose tags: `1girl, looking at viewer, standing, outdoors, cherry blossoms, school uniform, smile, ...`.
3. *Remove* tags describing intrinsic features the LoRA must memorize: `blue eyes, long black hair, twintails, hair ribbon, ahoge` etc. — otherwise these tags become required at inference and the model won't trigger the appearance from `mychar_xyz` alone.
4. Run `kohya_ss → Utilities → Captioning → Manual` or BooruDatasetTagManager for batch tag operations.

**For Pony V6** specifically, also prepend `score_9, score_8_up, score_7_up, source_anime,` to every caption (this matches V6 training distribution).

**For NoobAI v-pred** prepend `masterpiece, best quality, newest, absurdres, very awa,`.

**For Illustrious** the tag string is sufficient; no quality prefix mandated, but `masterpiece, best quality, absurdres` helps.

### C. Training configuration: concrete kohya_ss settings

**Profile 1 — RTX 3090 Ti (24 GB) — SDXL/Illustrious character LoRA (recommended baseline)**

```
Pretrained model: <Illustrious-XL-v2.0-stable.safetensors or Anim4gine v4 Opt>
LoRA Type: Standard
Mixed precision: bf16
Save precision: bf16
Cache latents: True   |  Cache latents to disk: True
Cache text-encoder outputs: True (saves ~2 GB; precludes TE training)
Network rank (dim): 16  (32 if multi-costume)
Network alpha: 8        (or 16; alpha = dim / 2 for "soft" LoRAs)
Conv rank/alpha: leave off for standard LoRA
Resolution: 1024,1024  | Enable bucket: True | min 512 / max 2048
Batch size: 4
Gradient checkpointing: False (you have the VRAM; faster training)
Gradient accumulation: 1
Optimizer: Prodigy
  optimizer_args = ["decouple=True","weight_decay=0.01",
                    "betas=0.9,0.99","use_bias_correction=True",
                    "safeguard_warmup=True"]
Learning rate: 1.0   (Prodigy auto-tunes)
LR scheduler: cosine_with_restarts (num_cycles=3)
LR warmup: 0
Max train steps: ~2000–2400  (or 10–15 epochs)
Network train: U-Net + TE with TE-LR multiplier 0.5  (or U-Net only if you cached TE outputs)
Min SNR gamma: 5
Noise offset: 0.0357   (Pony) / 0 (Illustrious — base used noise_offset=0)
Multires noise discount: 0.3 (alternative to noise_offset)
Flip augmentation: only if character is symmetric
Save every n epochs: 1
xFormers: True   |  No-half-VAE: True   |  Full bf16: True
```
Expected throughput on a 3090 Ti at 1024² batch 4: ~3.0–3.5 it/s (batched), ≈ 12 minutes per epoch on 30 images × 10 repeats. Total run ≈ 2–3 hours.

**Profile 2 — RTX 4080 Laptop (16 GB) — same goal**
Identical to Profile 1 except:
```
Batch size: 1 (or 2 with grad-ckpt + cached TE outputs)
Gradient checkpointing: True
Cache text-encoder outputs: True (mandatory)
Network train: U-Net only (--network_train_unet_only)
Optimizer: AdamW8bit  (more memory-stable than Prodigy at low VRAM)
  Learning rate (UNet): 3e-4  (Pony/Illustrious community sweet spot)
  TE LR: 0  (frozen; TE outputs cached)
LR scheduler: cosine
Mixed precision: bf16  |  Full bf16: True
Optional: --max_grad_norm 0  (avoids clipping issues with full_bf16)
Optional: SDPA backend (--sdpa) instead of xformers if xformers wheel missing
```
Expected throughput at 1024² batch 1: ~1.8–2.2 it/s, ≈ 25–30 min per epoch on the same dataset; total run 4–5 hours. To speed up further on the 4080, drop training resolution to 768² (Civitai data: 1024 is ~3× slower than 512, ~1.8× slower than 768) at the cost of small detail fidelity.

**Profile 3 — Pony V6 / Illustrious LyCORIS LoCon for character + style**
Same as Profile 1 but switch *Network type* → **LyCORIS/LoCon**, set `network_dim 16, network_alpha 8, conv_dim 8, conv_alpha 4`. Train ~10 % longer steps because LyCORIS converges slightly slower.

**Profile 4 — Flux.1-dev character LoRA (3090 Ti, optional)**
Use kohya `sd3-flux.1` branch with `flux_train_network.py`. From the kohya/Civitai community data:
```
--pretrained_model_name_or_path flux1-dev.safetensors
--clip_l clip_l.safetensors --t5xxl t5xxl_fp16.safetensors --ae ae.safetensors
--network_module networks.lora_flux
--network_dim 32 --network_alpha 32
--learning_rate 1e-4 --optimizer_type adamw8bit
--cache_latents --cache_text_encoder_outputs --apply_t5_attn_mask
--gradient_checkpointing --full_bf16 --mixed_precision bf16
--timestep_sampling sigmoid --model_prediction_type raw --discrete_flow_shift 3.0
--guidance_scale 1.0 --network_train_unet_only
--blocks_to_swap 14            # ↑ if OOM, ↓ if VRAM headroom
--max_train_epochs 10
```
On a 3090 Ti expect ~5–7 s/it at 1024² batch 1 (per Civitai community's RTX 3060 12 GB extrapolation: 1024² ≈18 s/it, batch swap dependent). On the 4080 16 GB use `--blocks_to_swap 22–28` and `--fp8_base`; train at 768² for usable speed.

### D. Inference workflow recommendations

**Preferred ComfyUI workflow for SDXL/Illustrious/NoobAI characters (single image):**
1. `Load Checkpoint` → Illustrious v2 (or NoobAI eps 1.1 / v-pred 1.0).
2. (Optional) `Patch Sage Attention KJ` (auto / triton on 3090 Ti, fp8 on 4080).
3. `Load LoRA` (your character) at strength 0.7–0.95.
4. Positive prompt: `mychar_xyz, 1girl, masterpiece, best quality, newest, absurdres, <scene>, <pose>, <lighting>` (Illustrious / NoobAI eps).
   - For NoobAI v-pred: `very awa, masterpiece, best quality, newest, highres, absurdres,` ...
   - For Pony V6: `score_9, score_8_up, score_7_up, source_anime, mychar_xyz, ...`.
5. Negative: `lowres, bad anatomy, bad hands, text, error, missing fingers, extra digits, fewer digits, cropped, worst quality, low quality, signature, watermark, username, blurry, jpeg artifacts, sketch, old, oldest`.
6. `KSampler`: Euler-A or DPM++ 2M Karras (eps); **Euler + zero-terminal-SNR** for v-pred. Steps 25–30, CFG 4–6 (3–5 for v-pred). Resolution 832×1216 portrait, 1024×1024, or 1216×832 landscape.
7. `VAEDecode` → `Image Upscale (4x-UltraSharp or NMKD-Siax)` → `KSampler` second pass at denoise 0.25–0.35 (latent hires fix).
8. `FaceDetailer` (Impact Pack) with `face_yolov8n.pt` and the same checkpoint+LoRA, denoise 0.30, separate resolution 1024², for clean anime faces.

**Tip:** Save this as a JSON template; ComfyUI lets you drag-drop a generated PNG to recover the entire graph because every node and seed is encoded as PNG metadata.

**Forge equivalents:** identical samplers; enable `Hires fix` (4x-UltraSharp, 0.25–0.35 denoise), `ADetailer` (face_yolov8n + optional hand_yolov8n), and `Dynamic CFG / CFG Rescale` extension at 0.2 for v-pred models.

### E. Tips and optimization tricks for your specific GPUs

**RTX 3090 Ti (24 GB, Ampere)**
- You will *never* be VRAM-limited for SDXL inference; run two ComfyUI workers, one with Illustrious + one with Flux Q8, behind a queue.
- For SageAttention, stick to `auto`/`triton`/`cuda` (FP16). FP8 mode is Ada-only and will crash.
- xFormers 0.0.27+ + PyTorch 2.4 bf16 + `--no-half-vae` is the most stable training config; you can leave gradient checkpointing *off* and run batch 4 at 1024², which yields ~30–40 % faster wall-clock training than batch 1+grad-ckpt.
- Use `torch.compile(mode="reduce-overhead")` in ComfyUI custom nodes (or the `--fast` ComfyUI flag with PyTorch ≥ 2.3) for ~10–15 % SDXL inference speedup.
- For Flux full-precision inference, you have just enough VRAM (~22 GB peak FP16); offload T5 to CPU via the Quanto or GGUF nodes if running with ControlNet.
- Power: 3090 Ti is a 450 W card; consider undervolting to 0.875 V @ 1830 MHz for ~85 % of stock perf at 60 % power — meaningfully better thermals over multi-hour LoRA runs.

**RTX 4080 Laptop (16 GB, Ada)**
- This is fundamentally the *minimum-comfortable* card for SDXL LoRA training. Treat 16 GB as a hard wall: always cache TE outputs, always grad-ckpt, always train UNet-only on first runs.
- Use **fp8 SageAttention** in ComfyUI for the largest single speedup available to you (Ada has dedicated fp8 tensor cores).
- For Flux training/inference, stick to **GGUF Q8_0 or fp8** loaders. Q8 quality is essentially fp16; Q4_K_M is the floor for character LoRA training.
- Laptops thermal-throttle hard: pin a fan curve, undervolt if BIOS allows, and use `--medvram-sdxl` style flags only if you actually OOM (default ComfyUI is more memory-efficient than A1111-medvram).
- For LoRA training, **set Windows pagefile to ≥ 64 GB** — cached latents+TE outputs+block-swap during Flux runs spill heavily to system memory.
- Battery: never train on battery. Even browsing while training will trigger Windows GPU power-state churn that slows iters by 20–40 %.
- Use **block-swap (kohya `--blocks_to_swap 22–28`)** if you ever attempt Flux LoRA; you'll trade RAM for VRAM and get ~2× the iteration time of a 3090 Ti, but it works.

### F. End-to-end "first character LoRA" checklist (1 weekend project)

1. Pick base: **Illustrious XL v2.0-stable** (most LoRA-compatible) or **NoobAI-XL Epsilon 1.1** (richest knowledge).
2. Collect 30–50 images of your character; resize/crop so the shorter side is ≥ 1024 px where possible.
3. WD14-tag with the `wd-swinv2-tagger-v3` ONNX model + character expansion.
4. Hand-prune captions: insert `mychar_xyz` first; delete intrinsic-feature tags.
5. Configure kohya as Profile 1 (3090 Ti) or Profile 2 (4080 Laptop).
6. Train ~2 000 steps; save every epoch.
7. Generate 9-image test grids per epoch in ComfyUI with fixed seeds; pick the epoch where likeness peaks before quality regresses.
8. Publish/use the LoRA at strength 0.75–0.9 with FaceDetailer post-processing.

A reasonable first-attempt converges in 2–3 hours on the 3090 Ti and 4–6 hours on the 4080 Laptop, including sample-grid generation.

---

## Caveats

- **Pony V7 (AuraFlow) is too new (Nov 2025)** for stable LoRA tooling as of the cutoff of the sources surveyed (Apatero, Civitai posts dated Nov–Dec 2025). I have not corroborated its training stack across multiple primary sources; treat the 7 B-param/AuraFlow numbers as accurate for the architecture decision but expect the training tooling and best-practice recipe to shift over the next 6 months. **For a project starting today, V6 + Illustrious is the safer bet; revisit V7 when kohya / SimpleTuner ship first-class AuraFlow support.**
- **Illustrious XL v2.0 fine-tune behavior**: OnomaAI explicitly markets v2.0 as the *most fine-tune-stable* version, but the early aesthetic ecosystem is still on v1.1. Some Civitai community posts recommend training LoRAs against v0.1 ("AnyIllustrious-XL for LoRA training" is a community-modified base specifically for trainers). If you find your v2.0-trained LoRA "fries" on v1.1 derivatives, retrain on v1.1 or AnyIllustrious.
- **NoobAI v-prediction sampling**: Karras schedules are *unsupported* on v-pred 1.0; using them produces saturated/gray outputs. Stick to Euler / DDIM with Zero Terminal SNR enabled. Several Civitai posts conflict on whether DPM++ 2M works — empirically it can, but only with the "automatic" or "SGM Uniform" schedule.
- **Flux LoRA portability across precisions**: SimpleTuner's docs warn that the precision the LoRA was trained at must match the precision used at inference (training int8-Quanto then loading on bf16 Flux can degrade). Train on whatever precision you intend to deploy.
- **fp8 on Ampere (3090 Ti)**: fp8 *weights* load fine via fp8-scaled or GGUF, but compute falls back to bf16/fp16. You get the VRAM savings, not the throughput, of fp8. Don't expect 4080-level fp8 speedups on the 3090 Ti.
- **Source-quality flag**: Several blog-style sources cited above (Apatero, propelrc, dataloop, mimicpc, redrta, prompthero) are SEO-driven aggregators that occasionally repeat numbers without primary verification. Where I quoted numerical figures (VRAM, training-time, parameter counts, image counts) I cross-checked against primary sources — kohya_ss/sd-scripts repo, Cagliostro Lab's official Animagine v4 release post, OnomaAI's Illustrious v2.0 release notes, the Pony Diffusion blog, the NoobAI HuggingFace card, Puget Systems' benchmark, the SimpleTuner Flux quickstart, and HuggingFace's official LoRA training blog. Treat secondary numbers (e.g., "Pony V7 = 7 B params, 10 M images") as approximate until a primary release post is available.
- **Legal/ethical**: NoobAI's license inherits the *fair-ai-public-license-1.0-sd* and explicitly **prohibits commercialization** of the model, derivatives, and outputs. Pony Diffusion's license has its own restrictions. Illustrious XL is more permissive but check the latest license at illustrious-xl.ai. Animagine 4.0 is CC BY-NC-SA. Plan your downstream use accordingly — if you intend commercial use, an SDXL-base LoRA (Stability's CreativeML Open RAIL++) may be the safest legal foundation despite weaker default anime quality.
- **Hardware lifespan**: Sustained 24/7 LoRA/DreamBooth training on consumer GPUs (especially the 3090 Ti at 450 W) accelerates VRM/fan wear. Puget Systems explicitly notes consumer cards "are not designed for long-term, sustained heavy loads." Undervolt, set fan curves, and avoid back-to-back overnight runs without breaks.