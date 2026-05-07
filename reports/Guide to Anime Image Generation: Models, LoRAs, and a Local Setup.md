# The Complete 2025–2026 Guide to Anime Image Generation: Models, LoRAs, and a Local Setup for ≥8 GB VRAM NVIDIA GPUs

If you want **the single most actionable answer** up front: in 2026 the state-of-the-art anime ecosystem revolves around **SDXL-derived anime base models — specifically Illustrious-XL, NoobAI-XL, Pony Diffusion V6 XL, and Animagine XL 4.0** — paired with **character LoRAs from CivitAI**, run locally via **Stable Diffusion WebUI Forge or ComfyUI**. For paid/closed services, **NovelAI Diffusion V4.5** remains the reference for tag-driven anime "character knowledge" (it natively recognizes thousands of named anime characters), while **Midjourney Niji 6** is best for stylized originals and **GPT-4o / DALL-E 3** is best for casual Ghibli-style transfers but actively refuses many copyrighted characters. FLUX.1 produces beautiful anime stylization through LoRAs but is **not** the right base model for faithful recreation of a specific named character — the open anime ecosystem (Danbooru-tag-trained SDXL forks) still owns that use case.

The rest of this report walks through every layer of that recommendation in concrete detail.

---

## 1. Paid / API-based Anime Image Generators

### 1a. The four services that matter for anime

| Service | Model (current) | Best at | Pricing (April 2026) |
|---|---|---|---|
| **NovelAI** | Diffusion V4.5 (Full / Curated) | Faithful named-character generation via Danbooru tags; multi-character composition; long T5 prompts (~512 tokens) | Tablet $10/mo, Scroll $15/mo, Opus $25/mo (unlimited normal-resolution gens). Free trial = ~30 generations |
| **Midjourney + Niji·journey** | Niji 6 | Original anime style, dynamic compositions, multi-character scenes, in-image text. Style/character references via `--sref` and `--cref` | Standard $30/mo, Pro $60/mo (Niji shares Midjourney subscription) |
| **OpenAI ChatGPT (GPT-4o native image gen)** | GPT-Image-1 / GPT-4o | Conversational editing, "make this Ghibli-style," text rendering | ChatGPT Plus $20/mo (~50 images/3-hr window). Refuses many copyrighted characters/living artists since the March-2025 Ghibli backlash |
| **Adobe Firefly** | Firefly Image 4 / Image Model 4 | Commercially safe anime style (trained only on licensed/Adobe-Stock data). Will *not* reproduce trademarked anime characters | Bundled in Adobe CC; standalone Firefly plans from ~$10/mo with generative credits |

Honorable mentions: **Leonardo.AI**, **PixAI** (anime-first, mobile-friendly, "Tsubaki.2" model launched March 2026), **SeaArt**, **Tensor.Art**, and **Yodayo / Moescape**. These are essentially hosted front-ends for the same open-source SDXL anime models discussed in §2 — useful if you don't want to install anything, but they don't beat the underlying open weights for quality.

### 1b. Quality and faithfulness comparison

For **faithful recreation of canonical anime characters** (Naruto in his Konoha jacket, Goku's Super Saiyan forms, Luffy's Gear 5, Tanjiro's Hanafuda earrings, Eren in ODM gear, etc.):

1. **NovelAI V4.5 Full** — best in class. The model is trained on the Danbooru tag system, so prompts like `1boy, uzumaki naruto, whisker markings, hokage cloak` produce instantly recognizable characters with no LoRA needed. V4.5 also added first-class multi-character support and natural-language prompts.
2. **Open-source Illustrious / NoobAI-XL / Pony locally** (see §2) — equal to or better than NovelAI when a community-trained LoRA exists for the character; the base models themselves know thousands of Danbooru-tagged anime characters out of the box.
3. **Niji 6** — produces high-quality original characters in *the style of* a series, but specific named characters tend to be approximations (Niji is not Danbooru-trained). The new `--cref` (character reference) helps with consistency across images.
4. **GPT-4o / DALL-E 3** — capable of producing the *style* (the Ghibli/Akira/Toriyama look) extremely well, but OpenAI's system card explicitly adds refusals for "the style of individual living artists" and increasingly for trademarked characters since March 2025.
5. **Adobe Firefly** — deliberately *cannot* recreate Goku, Naruto, Gojo, etc., because Adobe trains only on rights-cleared content. Use it only if you need commercially-licensed *anime-style original* art.

### 1c. Original anime art vs. licensed-character recreation

- **For original/inspired-by anime art with commercial safety:** Adobe Firefly is the only mainstream service that explicitly licenses outputs for commercial use.
- **For licensed-character look-alikes:** NovelAI is the cleanest paid option; locally hosted SDXL anime models with character LoRAs are the gold standard. Note that *imitating* a copyrighted character is a legal grey area in the U.S./EU/Japan; commercial use of a recognizable copyrighted character risks infringement claims regardless of how the image was made.

---

## 2. Open-source Base Models for Local Anime Generation

The anime-model landscape has gone through three eras: **SD 1.5 (2022–2023)**, **SDXL fine-tunes (2024)**, and **the "Illustrious / NoobAI / Pony" generation (late-2024 → 2026)**. As of April 2026, the SDXL-based anime ecosystem is still dominant; FLUX and SD 3.5 produce gorgeous stylization but lack the deep Danbooru-tag knowledge that drives faithful character work.

### 2a. SD 1.5 vs. SDXL vs. SD 3.5 vs. FLUX — what to actually use

| Family | VRAM | Anime maturity | Verdict |
|---|---|---|---|
| **SD 1.5** | 4 GB | Mature but legacy | Use only if you have an old GPU. AnythingV5, AbyssOrangeMix3 (AOM3), MeinaMix, Counterfeit-V3 still work. |
| **SDXL (1024×1024 native)** | 6–8 GB | **Dominant in 2026** | This is where you want to be. |
| **SD 3.5 Medium / Large** | 10–24 GB | Sparse (license issues + flow-matching DiT difficulty) | A few experimental anime fine-tunes (alfredplpl's `sd3-5-large-modern-anime-full`, suzushi's `miso-diffusion-m`, `Hamachi_SD3.5M`) but no community-dominant model |
| **FLUX.1 [dev] / [schnell]** | 12 GB+ (8 GB possible with NF4/GGUF quantization) | Excellent for anime *style* via LoRAs, weak on named-character knowledge | Use it when you want photoreal-quality anime aesthetics; layer character LoRAs on top |

**For a ≥8 GB VRAM card, the answer is: SDXL-based anime checkpoints.** Specifically a model from the Illustrious or NoobAI lineage.

### 2b. The SDXL anime checkpoints you actually want (April 2026)

All of these are free downloads from CivitAI or Hugging Face. File size for a fp16 SDXL checkpoint is ~6.5 GB. They run comfortably on 8 GB VRAM in Forge or ComfyUI (~30–45 s per 896×1152 image on an RTX 3060/4060).

**Tier 1 — Modern Danbooru-tag base models (best character knowledge):**

- **Illustrious-XL v0.1 / v1.0 / v1.1 / v2.0** — by OnomaAI Research. Built on Kohaku-XL Beta, trained on Danbooru up to mid-2024, native 1536×1536. The de-facto base for thousands of community fine-tunes. CivitAI: `civitai.com/models/795765/illustrious-xl`. v2.0 page: `civitai.com/models/1369089/illustrious-xl-20`.
- **NoobAI-XL (NAI-XL)** by Laxhar Lab — full Danbooru + e621 dataset, two prediction modes (Epsilon-pred 1.1 and V-pred 1.0). 122 K downloads, 5.6 M generations. CivitAI: `civitai.com/models/833294`. **This is currently the deepest character/artist tag knowledge in any open model.** V-pred variants need ComfyUI/Forge Classic/reForge — not vanilla A1111.
- **Animagine XL 4.0 / 4.0 Opt / 4.0 Zero** — by Cagliostro Research Lab, retrained from SDXL 1.0 on 8.4 M anime images (knowledge cutoff Jan 7, 2025), 2,650 GPU hours. Use 4.0 Opt for general use, 4.0 Zero as a base for LoRA training. CivitAI: `civitai.com/models/1188071` ; HF: `huggingface.co/cagliostrolab/animagine-xl-4.0`.
- **Pony Diffusion V6 XL** — by PurpleSmartAI, ~2.6 M images, score-tag quality system (`score_9, score_8_up, score_7_up`). Despite the name, it generates exceptional anime, cartoon, furry, and 3D content. CivitAI: `civitai.com/models/257749`. **Different "lineage" from Illustrious — Pony LoRAs are not interchangeable with Illustrious LoRAs.**
- **Kohaku-XL (Beta / Gamma / Delta / Epsilon / Zeta)** — KBlueLeaf's research-grade lineage, the basis Illustrious was built on. HF: `huggingface.co/collections/KBlueLeaf/kohaku-xl`. Excellent for 2200+ specific characters via Danbooru tags.
- **Chenkin Noob XL (CKXL)** v0.5 — extends NoobAI 1.1 with ~12 M images including Danbooru up to Jan 2026; sharper character fidelity, better game-art / Western style. CivitAI: `civitai.com/models/2167995`.

**Tier 2 — Popular community merges (often higher aesthetic appeal than the bases):**

- **WAI-NSFW-illustrious-SDXL** v17 — `civitai.com/models/827184`. One of the highest-rated anime models on CivitAI.
- **Nova Anime XL / Nova 3DCG / Nova Unreal** by Crody — `civitai.com/models/376130`. Nova Anime gives a cleaner 2D style; Nova 3DCG mimics figurine renders; Nova Unreal is semi-realistic.
- **NTR MIX | illustrious-XL | Noob-XL** XIII — `civitai.com/models/926443`. Excellent default look with strong LoRA compatibility.
- **Mistoon_Anime** v1.0 (NoobAI / Illustrious / Pony bases) — `civitai.com/models/24149`. Bright "cartoony" 2D anime style.
- **Holy Mix [illustriousXL]** v1 — `civitai.com/models/959490`. High-contrast clean anime.
- **Prefect Pony XL** v6 — `civitai.com/models/439889`. 4.3 M downloads, one of the most-loved Pony fine-tunes.
- **AniVerse Pony XL / AniVerse Illustrious** — strong 2.5D realism-tinged anime.
- **AnyLoRA / AnythingXL** — meant as merge bases; useful when training your own LoRA.

**Tier 3 — Legacy SD 1.5 anime models (if you're on a 4 GB GPU):**

- **AnythingV5 / V3** — `civitai.com/models/9409`
- **AbyssOrangeMix3 (AOM3)** — WarriorMama777, `huggingface.co/WarriorMama777/OrangeMixs`
- **Counterfeit-V3** — gsdf, painterly anime style
- **MeinaMix** family — beloved soft anime style
- **CounterfeitXL** — the SDXL successor

### 2c. Character faithfulness vs. style transfer — which model for which job

- **Faithful named-character recreation (Naruto, Goku, Luffy, Tanjiro, Eren, Asuka…):** Pick a Danbooru-trained base — **NoobAI-XL Epsilon 1.1** or **Illustrious v2.0** or **Animagine XL 4.0 Opt** — and prompt with the canonical Danbooru tag (`uzumaki naruto`, `son goku`, `monkey d. luffy`, `kamado tanjirou`, `eren yeager`). Add a community LoRA only when the model's built-in knowledge is incomplete or when you need a specific outfit/form.
- **Style transfer / "make X look like anime Y":** Pick an artist-tag-rich base (NoobAI is best) and use artist tags (`by toriyama akira`, `by oda eiichirou`, `by isayama hajime`) plus optionally a series-style LoRA. For img2img style transfer, combine the base with **ControlNet Lineart-Anime + Tile** (see §4f).
- **Original anime-style art with high prompt adherence:** **Illustrious XL v2.0** (best natural-language support among anime SDXLs) or **FLUX.1 [dev] + an anime LoRA** if you have ≥12 GB VRAM and want T5-level prompt understanding.

### 2d. VRAM requirements (single-image generation, fp16, no batching)

| Model | Minimum VRAM | Comfortable VRAM | Notes |
|---|---|---|---|
| SD 1.5 fine-tunes | 2 GB (Forge) | 4 GB | 512×768 native |
| SDXL anime (Illustrious/NoobAI/Pony/Animagine) | 4 GB (Forge) | 8 GB | 1024×1024 native; 1536×1536 for IL v1+ |
| SD 3.5 Medium | 8 GB | 12 GB | Ships with three text encoders |
| SD 3.5 Large | 16 GB | 24 GB | Or use fp8/NF4 quant |
| FLUX.1 [dev] fp16 | 24 GB | 24 GB | T5-XXL is the bottleneck |
| FLUX.1 [dev] NF4 / GGUF Q4 / fp8 | 6–8 GB | 12 GB | Forge supports NF4 natively |

On 8 GB VRAM, your sweet spot is **any SDXL anime model + Forge UI**, which Lllyasviel benchmarks at 30–45% faster inference and 700 MB–1.3 GB lower peak VRAM than vanilla A1111.

---

## 3. Character LoRAs and Fine-tuned Weights for Specific Anime Franchises

### 3a. How character LoRAs work

A LoRA (Low-Rank Adaptation) is a small adapter file (typically 50–250 MB for SDXL, ~7–18 MB for ultra-low-rank dim-1 LoRAs) that injects new weight deltas into a base checkpoint at inference time. For anime characters they typically encode:

- the character's hair color, eye color, distinctive markings (whiskers, scars, slit pupils)
- canonical outfit(s) and accessories
- iconic poses or "forms" (Super Saiyan, Gear 5, Titan form, breathing techniques)

You activate them with a **trigger word** in the prompt and a **weight** between 0.5 and 1.5 — most character LoRAs converge on the **0.7–1.0** range. In A1111 / Forge syntax: `<lora:son_goku_offset:0.85>`. In ComfyUI: a `Load LoRA` node chained between your checkpoint and KSampler with `strength_model` and `strength_clip` sliders.

### 3b. Where to get pre-trained character LoRAs

- **CivitAI** (`civitai.com`) — by far the largest library; filter by "Base Model: Illustrious / NoobAI / Pony / SDXL 1.0 / SD 1.5" and by category "Character." Tens of thousands of anime character LoRAs.
- **Hugging Face** — search `tag:lora anime`. WiroAI publishes high-quality FLUX character LoRAs (e.g. `WiroAI/Goku-Dragon-Ball-Flux-LoRA`); prithivMLmods publishes anime-style FLUX adapters (e.g. `prithivMLmods/Canopus-LoRA-Flux-Anime`).
- **Tensor.Art**, **SeaArt**, **PixAI**, **Shakker** — mostly mirrors of CivitAI; useful for in-browser previews. Note that SeaArt has been accused of mirroring without permission.
- **arcenciel.io** — newer creator-focused community.

### 3c. Concrete LoRAs for the franchises you mentioned

| Franchise | Recommended LoRA(s) | Base | CivitAI URL slug |
|---|---|---|---|
| **Naruto** | "Uzumaki Naruto" by Konan (SD 1.5, weight 0.8–1.0, trigger `uzumaki naruto`); "Naruto Uzumaki" by Illustrious_Bloc (Illustrious); Sakura Haruno IllustriousXL by Konan; Tsunade SDXL by ethensia; Konan, Kurenai, Ino Yamanaka by Konan | SDXL/Illustrious | /models/202728, /models/453431, /models/816501, /models/924509, /models/15520 |
| **Dragon Ball** | "Son Goku - Dragon Ball - Flux1.D & SDXL" by PhotobAIt; "Son Goku (All Series) LoRA" by Lykon; "Son Goku - Dragon Ball - Illustrious v1.0" by TheBlackPrince; "Goku super saiyan 3" SDXL; "Android 18" by SysDeep (SD15/Pony/SDXL/Illustrious); "Dragon Ball Style" v3 SDXL; "Akira Toriyama Style" LoRA | Multi | /models/239649, /models/18279, /models/1108143, /models/345197, /models/160086, /models/474074, /models/4857 |
| **One Piece** | "Monkey D. Luffy & Roronoa Zoro / Egghead Outfit" Illustrious by 25kk; "Gear Fifth Luffy" by Lykon (SD 1.5); "One Piece (Wano Saga) Style LoRA"; "One Piece Manga Style" Illustrious; Alvida East-Blue Arc Illustrious | Multi | /models/1104324, gear-fifth listing, /models/4219, tensor.art /models/824896435662118326 |
| **Demon Slayer (Kimetsu no Yaiba)** | "Demon Slayer Style and Characters | All-in-One LoRA" v1.0 SDXL — covers Tanjiro, Nezuko, Zenitsu, Inosuke, Rengoku, Uzui, Genya, Muichiro, Mitsuri, the Hashira, and the swordsmiths in one Pony LoRA; "Inosuke Hashibira" Pony by novowels; "Kanae Kocho" Pony by novowels; "Mitsuri Kanroji" SDXL Realistic & Anime by PhotobAIt; "Kimetsu no Yaiba Anime Style LoRA (Pony)" v0.1 | Pony / SDXL | /models/514040, /models/770893, /models/568217, /models/629412, /models/421263 |
| **Attack on Titan (Shingeki no Kyojin)** | "Eren Yeager | Shingeki no Kyojin" Illustrious v0.1 by Konan; "Shingeki no Kyojin Anime Style LoRA" Illustrious s4; "Attack on Titan Face" v3.0 Illustrious; Historia Reiss Illustrious dim-1 mini-LoRA; Female Titan Illustrious | Illustrious | /models/374004, /models/434270, /models/1560315, /models/1589917, /models/1622781 |

A practical workflow for *any* franchise: open CivitAI → Models → filter "Character" + the base you're using → search the character's name. Read the LoRA's description for **trigger words** and **recommended weight** before generating. Most authors include sample prompts you can copy.

### 3d. Train your own character LoRA

If a character isn't covered (or only has a low-quality LoRA), train one yourself. The 2026 stack:

- **kohya_ss GUI** by bmaltais — `github.com/bmaltais/kohya_ss`. Still the most reliable, parameter-rich GUI. Install via `Stability Matrix` (`github.com/LykosAI/StabilityMatrix`) for one-click setup.
- **OneTrainer** — competitive alternative with cleaner UI.
- **FluxGym** (containerized via Pinokio) — easiest entry point for FLUX LoRAs.
- **Civitai's built-in trainer** — no install at all; you upload images, pay Buzz, get a LoRA back. Great for casual characters.

**Minimum data and settings (SDXL character LoRA on a 12 GB+ GPU; 8 GB possible with fp8 mode):**

- 20–80 images of the character covering varied poses, expressions, outfits, and angles
- Resolution 1024×1024 (or 768×1152 for portrait subjects); enable bucketing to keep aspect ratios
- Caption with WD14 (Booru tags) — *prefix* with the trigger word (e.g. `chrnzu_eren, ...rest of tags...`); *prune* tags for the character's intrinsic features (hair color, eyes, scars) so they bind to the trigger
- Network dim 16–32, alpha = dim/2 (character LoRAs); style LoRAs can use dim 64–128
- Optimizer: Prodigy or AdamW8bit. LR ~5e-4 (Prodigy auto-adjusts); text encoder LR off or 1/10 of UNet
- Batch 2, ~10–20 epochs, ~1500–4000 total steps. Save every 1–2 epochs and pick the best checkpoint
- Train against the *base* you'll use (Illustrious 0.1 for Illustrious LoRAs; Pony V6 for Pony LoRAs; Animagine 4.0 Zero for Animagine LoRAs). LoRAs do **not** transfer across these lineages.
- For 8 GB VRAM specifically: enable fp8 base model, gradient checkpointing, and `--mixed_precision=fp16`. A 50-epoch run on 20 images takes ~15 minutes on a 4060 Ti 16 GB; ~25 minutes on an 8 GB card.

For **FLUX LoRA training**, the Hugging Face `flux-qlora` blog shows you can fine-tune FLUX.1-dev with bitsandbytes 4-bit quantization at ~37 GB peak VRAM (on cloud) or rent an A100/H100 on Modal or RunPod for $1–2 of compute. The `train_dreambooth_lora_flux.py` script in `diffusers` is the canonical recipe; rank 16, 4000 steps, LR 2e-4 is a known-good preset.

### 3e. Stacking multiple LoRAs

Rules of thumb learned from the community:

1. **Style + character is the safe combo.** A style LoRA at 0.4–0.7 plus a character LoRA at 0.7–1.0 rarely fights.
2. **Two character LoRAs in the same image is risky** — they share the same `1girl`/`1boy` token slot. Use ComfyUI's **regional prompter** or **Latent Couple** to spatially mask each LoRA's influence.
3. **Check base-model lineage compatibility.** Pony LoRAs do not work on Illustrious checkpoints (different CLIP layout). Illustrious LoRAs *mostly* work on NoobAI checkpoints (same Kohaku-XL ancestor).
4. **Lower CLIP strength first.** If a LoRA is dominating the prompt, reduce `strength_clip` before `strength_model`.
5. **8 GB VRAM:** you can comfortably stack 3–5 LoRAs at SDXL resolution. Each adds ~0.1–0.3 GB.
6. **For permanent combinations**, merge LoRAs into a single LoRA via SuperMerger (A1111 extension) or Kohya's merge scripts — saves VRAM, simpler workflow.

---

## 4. Full Local Setup Guide for an NVIDIA GPU ≥ 8 GB VRAM (Windows / Linux)

### 4a. Choosing your UI: ComfyUI vs A1111 vs Forge

| UI | Strength | Weakness | Best for |
|---|---|---|---|
| **AUTOMATIC1111 (vanilla A1111)** | Massive extension ecosystem, simplest learning curve | Slowest backend; barely works with FLUX; project is essentially in maintenance mode | Beginners who only need SD 1.5 / SDXL and follow YouTube tutorials |
| **Stable Diffusion WebUI Forge** by lllyasviel | A1111-style UI, ~30–45% faster on SDXL, 700 MB–1.3 GB lower VRAM peak, supports FLUX (NF4/GGUF), supports SD 1.5 on 2 GB / SDXL on 4 GB. Recommended default for most users | Some A1111 extensions don't work; the project moves fast and occasionally breaks | **Most users in 2026 — recommended default** |
| **reForge** (by Panchovix) | A Forge fork that stays closer to A1111 compatibility, preserves civitai-compatible model hashes; supports FLUX | Slightly behind Forge on the absolute newest models | Users who want Forge speed without losing A1111 features |
| **ComfyUI** | Node-based; first to support every new model (FLUX, Wan 2.x, HunyuanVideo, Kontext); maximum control; best for complex multi-LoRA / multi-ControlNet pipelines | Steeper learning curve | Power users; anyone doing video, advanced inpainting, or production pipelines |

**My recommendation for the user:** Install **Forge** as your daily driver. Install **ComfyUI** in parallel when you graduate to multi-stage workflows. Skip vanilla A1111.

### 4b. Installing Forge (Windows)

1. Download `webui_forge_cu121_torch231.7z` (or the latest CUDA 12.4 build) from `github.com/lllyasviel/stable-diffusion-webui-forge` — the "one-click installation package" link in the README.
2. Extract with 7-Zip to a path **without spaces** (e.g. `D:\AI\forge\`). The package bundles Python 3.10 and PyTorch — you don't need to install them separately.
3. Run `update.bat` first (downloads the latest commits).
4. Run `run.bat`. It launches at `http://127.0.0.1:7860`.
5. RTX 50-series only: you'll see a `sm_120 not compatible with current PyTorch` error; update PyTorch to the nightly CUDA 12.8 build (the GitHub Issues thread has the exact pip command).

### 4c. Installing ComfyUI (Windows)

Two paths:

- **ComfyUI Desktop** (`comfy.org/download`) — installer-style, auto-updates, includes Python + CUDA. Recommended for new users on Windows/Mac with NVIDIA GPUs.
- **ComfyUI Portable** — download `ComfyUI_windows_portable_nvidia.7z` from the GitHub releases, extract, double-click `run_nvidia_gpu.bat`. Then install **ComfyUI-Manager** by saving `scripts/install-manager-for-portable-version.bat` to your portable folder and running it — this gives you one-click missing-node installation.

For Linux: clone the repo, create a venv, `pip install -r requirements.txt`, run `python main.py`.

### 4d. Installing checkpoints, LoRAs, VAEs, ControlNets

The directory layout is the same in Forge / A1111 / ComfyUI:

```
webui/                          (or ComfyUI/)
├── models/
│   ├── Stable-diffusion/       ← .safetensors checkpoint files go here
│   ├── Lora/                   ← LoRAs go here
│   ├── VAE/                    ← VAE files go here
│   ├── embeddings/             ← Textual Inversions / EasyNegative go here
│   ├── ControlNet/             ← ControlNet models go here
│   └── ESRGAN/  or  upscale_models/  ← upscaler .pth files
```

To **share models between Forge/A1111 and ComfyUI**, edit `ComfyUI/extra_model_paths.yaml` to point at your A1111/Forge `models` directory — saves disk space.

To **load a LoRA** in Forge/A1111: type `<lora:filename:0.8>` anywhere in the prompt; or click the 🎴 "Show extra networks" button and click the LoRA card. To **load a LoRA in ComfyUI**: insert a `Load LoRA` node between your `Load Checkpoint` node and your `KSampler`; chain multiple `Load LoRA` nodes for stacking. Always set `strength_model` and `strength_clip` (default 1.0; reduce to 0.6–0.8 for character LoRAs that overwhelm the prompt).

### 4e. Recommended generation settings for anime SDXL

These are 2025/2026 community consensus values that work across Illustrious / NoobAI-Eps / Animagine 4.0 / WAI / Nova-Anime:

| Setting | Recommended | Notes |
|---|---|---|
| **Resolution** | 832×1216 (portrait), 1216×832 (landscape), 1024×1024 (square) | Illustrious v1+ supports 1536×1536; lower-VRAM cards stay at 1024 |
| **Sampler** | **Euler a** (Illustrious / Animagine), **Euler** (NoobAI V-pred), **DPM++ 2M** or **DPM++ SDE** (Pony) | NoobAI V-pred *does not* support Karras schedulers |
| **Scheduler** | **Karras** (most cases), **SGM Uniform** (NoobAI V-pred + 4-step LCM/DMD2 LoRA), **Beta** (FLUX) | |
| **Steps** | 25–30 (Illustrious), 28 (Animagine), 20–28 (Pony), 6–16 (with LCM/DMD2 LoRA) | Bumping above 30 rarely helps |
| **CFG scale** | **5.0–6.0** for Illustrious/NoobAI/Animagine; **6–8** for Pony with score tags; **1.0–2.0** for FLUX; **1.0–1.5** for LCM/Lightning | Pony's score system internalizes CFG so you can run lower than you'd think |
| **CLIP skip** | **2** for SD 1.5 anime models; **1** (default) for SDXL/Illustrious/Pony | |
| **Hi-Res Fix / 2nd-pass upscaling** | Denoising 0.3–0.5, 10–20 hires steps | Use 4x-AnimeSharp or 4x-UltraSharp as the upscaler |

### 4f. VAE recommendations

Most modern SDXL anime checkpoints (Illustrious, NoobAI, Animagine, Pony, all of Crody's "Nova" series) **bake the VAE into the checkpoint** — set VAE to "Automatic" and you're done. If colors look washed-out or muddy, try:

- **SDXL VAE fp16-fix** by madebyollin — `huggingface.co/madebyollin/sdxl-vae-fp16-fix`. Fixes the well-known SDXL VAE NaN issue on fp16.
- **kl-f8-anime2** (Waifu Diffusion VAE) — `huggingface.co/hakurei/waifu-diffusion-v1-4/blob/main/vae/kl-f8-anime2.ckpt` — *only* for SD 1.5 anime models. Most vibrant.
- **NAI / Anything VAE** — `vae-ft-mse-840000-ema-pruned.ckpt` — also SD 1.5 only.

### 4g. Upscaling anime images

ESRGAN-class upscalers, all available on `openmodeldb.info` and `huggingface.co/Kim2091/AnimeSharp`:

- **4x-AnimeSharp** (Kim2091) — the reference for line-art-heavy anime; CivitAI: `civitai.com/models/1017531/4x-animesharp`
- **4x-UltraSharp** (lokCX) — best generalist; `civitai.com/models/116225`
- **R-ESRGAN 4x+ Anime6B** — bundled with Forge/A1111; great for soft anime
- **4x_NMKD-Siax_200k** and **4x_foolhardy_Remacri** — strong on line clarity; Remacri is the LoRA-author favorite
- **4x APISR** — a 2024 anime-specific model (ESRGAN/GRL variants)

Workflow: drop the `.pth` file into `models/ESRGAN/` (or `models/upscale_models/` in ComfyUI). In Forge/A1111, enable **Hi-Res Fix** with the upscaler set to "4x-AnimeSharp" or "R-ESRGAN 4x+ Anime6B," 1.5–2× scale, denoise 0.3–0.5. Or for finished images, use the **Extras** tab for pure ESRGAN upscaling.

### 4h. ControlNet for pose, composition, and style control

For SDXL anime workflows in 2026:

- **xinsir/controlnet-union-sdxl-1.0 (Union ProMax)** — single ControlNet model that handles canny, depth, openpose, scribble, softedge, lineart in one file. The most VRAM-efficient way to do ControlNet on 8 GB. HF: `huggingface.co/xinsir/controlnet-union-sdxl-1.0`.
- **xinsir/controlnet-openpose-sdxl-1.0** — best dedicated openpose for SDXL.
- **Eugeoter / Laxhar's NoobAI-XL ControlNet collection** — `huggingface.co/collections/Laxhar/noobai-sdxl-controlnet` — anime-specific canny, depth, lineart-anime, scribble, softedge, tile (only choice for V-pred NoobAI).
- **Illustrious ControlNet suite** (`illustriouscontrolnet.xyz`) — Tile, OpenPose, SoftEdge trained natively on Illustrious latents; cleaner colors than generic ControlNets.
- **Anytest v4.1 / MistoLine** — for stylized line-to-color workflows.

Use cases:

- **Pose control:** OpenPose ControlNet + a posed skeleton (use `OpenPoseAI.com` or the ComfyUI custom node `ComfyUI-OpenPose-Editor`).
- **Faithful style transfer of an existing image:** Tile + Lineart-Anime, denoise 0.5–0.7.
- **Character consistency across images:** IP-Adapter (`h94/ip-adapter-faceid-plusv2-sdxl`) or FaceID workflows.
- **Manga inking / coloring:** Lineart-Anime + a style LoRA.

### 4i. Recommended end-to-end workflow for faithful anime character recreation

```
1. Pick a base: Illustrious-XL v2.0, NoobAI-XL Eps 1.1, or Animagine 4.0 Opt
2. Pick a character LoRA from CivitAI matching that base
3. Prompt structure (Animagine's tag-order is the proven template):
   <subject count>, <character tag>, <series>, <rating>,
   <general descriptive tags>, <quality tags last>
   e.g. "1boy, son goku, dragon ball, super saiyan, blonde hair,
        green eyes, fighting stance, dynamic angle, masterpiece,
        best quality, very aesthetic, absurdres, newest"
4. Negative prompt: "lowres, worst quality, low quality, bad anatomy,
   bad hands, missing fingers, extra digits, jpeg artifacts, signature,
   watermark, username, blurry"
   (Add EasyNegativeXL embedding at weight 0.6–0.8 if you have it)
5. Sampler Euler a, Karras schedule, 28 steps, CFG 5.0,
   832×1216, CLIP skip 1, VAE automatic
6. Generate; pick the best seed; enable Hi-Res Fix
   with 4x-AnimeSharp at 1.5×, denoise 0.4, 12 hires steps
7. Optional: ADetailer extension to fix faces/hands automatically
8. Optional: ControlNet OpenPose to lock the character into a specific pose
```

### 4j. Useful Forge/A1111 extensions specifically for anime

- **ADetailer** — auto-detects faces/hands and inpaints them. Required for clean character work.
- **SD WebUI Tag Autocomplete** — Booru-tag autocomplete; essential for Illustrious/NoobAI/Pony.
- **sd-webui-prompt-all-in-one** — visual tag manager, weight sliders.
- **Infinite Image Browsing** — browses your generation history with metadata.
- **CivitAI Helper** — download LoRAs/checkpoints + thumbnails directly from the CivitAI URL.
- **APG-now-your-CFG** (reForge / Forge) — improves coherence at low CFG for v-pred models.
- **Sliding Window Guidance** — pairs nicely with Euler a at 25–45 steps.

---

## 5. Current State of the Art (2025–2026)

### 5a. Has FLUX.1 / SD 3.5 changed the anime landscape?

**Mostly no, with one caveat.** As of April 2026:

- **FLUX.1 [dev]** has produced excellent *anime-style* LoRAs (`prithivMLmods/Canopus-LoRA-Flux-Anime`, `WiroAI/Goku-Dragon-Ball-Flux-LoRA`, `alfredplpl/flux1-dev-modern-anime-lora`, dozens more on CivitAI under "Flux1.D" base). FLUX shines at painterly/Ghibli-style output with strong prompt adherence and clean text rendering. **However**, FLUX has weak Danbooru-tag knowledge — it does not "know" thousands of named characters the way NoobAI or Illustrious does, so it relies on character LoRAs for everyone.
- **SD 3.5** has had limited anime adoption due to (a) flow-matching training instability that the community found difficult, and (b) the Stability AI Community License's commercial restrictions chilling fine-tunes. A few experimental attempts exist (alfredplpl's full fine-tune of SD 3.5 Large, suzushi's `miso-diffusion-m`, FA770's `Hamachi_SD3.5M_v008A`) but no community-dominant model has emerged.
- **Qwen-Image-2512** (ByteDance / Alibaba), **Seedream 5.0**, and **HiDream** are strong newcomers with anime capability through their hosted APIs (Runware, etc.), but their open-weight ecosystems are nascent.

The verdict: **for faithful anime character work, the SDXL anime ecosystem (Illustrious + NoobAI + Pony + Animagine + their thousands of LoRAs) remains the state of the art for local generation.** This is acknowledged even by ComfyUI documentation guides — the anime base remains SDXL.

### 5b. New models specifically targeting anime character faithfulness

- **NoobAI-XL V-pred 1.0** (Dec 2024, still receiving updates) — the deepest Danbooru tag knowledge available openly.
- **Illustrious-XL v2.0 / 2.5** — better natural-language understanding, native 1536², explicit goal of being a robust LoRA-training base.
- **Animagine XL 4.0 Opt** (Feb 2025) — Cagliostro Lab's most polished anime base.
- **ChenkinNoob-XL v0.5** (Apr 2026) — extends NoobAI 1.1 with Danbooru data through Jan 2026 and 2.17 M Western/game-art images.
- **NovelAI Diffusion V4.5** (closed, paid) — currently the highest-fidelity character recall and the only model with first-class multi-character composition through Anlatan's proprietary T5-tokenized prompt format.
- **Tsubaki.2** (PixAI, March 2026) — anime-first proprietary model with character-consistency tools.

### 5c. Community resources

- **Reddit:** r/StableDiffusion (general), r/comfyui, r/PromptDesign, r/aiArt. There is **no** unified r/AnimeAI subreddit, but r/StableDiffusion threads daily about Illustrious, NoobAI, Pony.
- **Discord:** the **Stable Diffusion Discord** (328 K members, `discord.com/invite/stablediffusion`); Cagliostro Lab Discord (`discord.gg/cqh9tZgbGc`); Pony Diffusion server; NovelAI's official server (no discussion of running NAI weights locally — they ban for that).
- **Model aggregators:** **CivitAI** (`civitai.com`) is the central hub; **CivArchive** (`civarchive.com`) preserves models removed from CivitAI; **OpenModelDB** (`openmodeldb.info`) for upscalers; **Hugging Face** for research/official releases.
- **Documentation / tutorials:** stable-diffusion-art.com (Andrew Zhu), civitai.com/articles, comfyui-wiki.com, techtactician.com, education.civitai.com, kblueleaf.net (Kohaku-XL author's blog), cagliostrolab.net (Animagine deep guides), seaart.ai/articleDetail (community guides translated to English).
- **Training:** Holostrawberry's articles on arcenciel.io, Furkan Gözükara's Stable-Diffusion GitHub repo (low-VRAM training tutorials), Civitai's "A Fresh Approach to SDXL & Pony XL Lora Training" article.

### 5d. Note on legality and ethics

Imitating a copyrighted anime style or character through AI is a contested legal area. OpenAI added refusals for "in the style of individual living artists" after the March-2025 Studio Ghibli backlash; Adobe Firefly refuses to generate trademarked anime characters by design; Japanese lawmakers (House of Representatives Cabinet Committee, April 16, 2025) have publicly stated that *style* alone is not protected under Japanese copyright but *content that is similar to or dependent on existing works* may infringe. In the U.S. and U.K., commercial use of recognizable copyrighted characters is generally infringement regardless of how the image was produced. For personal, non-commercial fan art the practical risk has historically been low, but caution is warranted whenever you publish or monetize.

---

## TL;DR Recommendation for the Reader's Setup

You have a ≥8 GB NVIDIA GPU. Here is the exact setup that produces the best faithful anime character recreations and clean style transfer:

1. **Install Stable Diffusion WebUI Forge** (one-click 7z from lllyasviel's GitHub). Add ComfyUI Portable later when you need advanced workflows.
2. **Download two checkpoints** to `models/Stable-diffusion/`:
   - **NoobAI-XL Epsilon-pred 1.1** (best Danbooru/character knowledge) — `civitai.com/models/833294`
   - **Animagine XL 4.0 Opt** (cleaner default look, great prompt template) — `civitai.com/models/1188071`
3. **Download upscalers** to `models/ESRGAN/`: **4x-AnimeSharp** and **4x-UltraSharp**.
4. **Download ControlNet:** **xinsir/controlnet-union-sdxl-1.0** to `models/ControlNet/` — covers all preprocessor types in one file.
5. **Install extensions:** ADetailer, SD WebUI Tag Autocomplete, CivitAI Helper, sd-webui-prompt-all-in-one.
6. **For each franchise you care about**, browse CivitAI for character LoRAs whose "Base Model" matches your chosen checkpoint (Illustrious or NoobAI-Eps if you went that route). Place files in `models/Lora/`.
7. **Default generation settings:** Euler a, Karras, 28 steps, CFG 5.0, 832×1216, CLIP skip 1, ADetailer enabled with `face_yolov8n.pt`, Hi-Res Fix at 1.5× with 4x-AnimeSharp, denoise 0.4.
8. **Prompt structure:** `1boy/1girl, <character_tag>, <series>, <descriptive tags>, masterpiece, best quality, amazing quality, very aesthetic, absurdres, newest`. Negative: standard `lowres, worst quality, low quality, bad anatomy, bad hands, signature, watermark, blurry`.
9. **Stack at most one style LoRA (0.4–0.7) and one character LoRA (0.7–1.0)** at a time. Validate each LoRA solo before stacking.
10. **For paid/cloud convenience** when you don't want to run anything: subscribe to **NovelAI Opus ($25/mo)** for the closest paid equivalent of this local setup with first-class character knowledge; or **Niji 6** ($30/mo for original anime style); avoid Adobe Firefly and DALL-E for character recreation.

This stack — open-source SDXL anime checkpoints + community LoRAs + Forge or ComfyUI on a modest NVIDIA GPU — is the same configuration the most prolific creators on CivitAI, Tensor.Art, PixAI, and SeaArt are using, and as of April 2026 it remains the best balance of quality, control, character faithfulness, and cost for anime image generation.