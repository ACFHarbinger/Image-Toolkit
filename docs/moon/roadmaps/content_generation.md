# Content Generation Roadmap — Anime Image & Video

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [0. Current State](#0-current-state-what-already-exists)
- [1. Image Generation](#1-image-generation)
- [2. Video & GIF Generation](#2-video-gif-generation)
- [3. Fine-Tuning Pipeline (4K video → character LoRA)](#3-fine-tuning-pipeline-4k-video-character-lora)
- [4. Hardware-Aware Deployment](#4-hardware-aware-deployment)
- [Phased Execution Sequence](#phased-execution-sequence)
- [Effort × Impact Matrix](#effort--impact-matrix)

---

## Implementation Timeline

> **Legend** — *Node fill:* new feature (blue) · augmentation (violet) · infrastructure (cyan) · research (slate) · integration (pink) — *Node border:* ✅ complete (green, thick) · ⬜ planned (slate, thin) — *Edges:* `==>` critical blocking dependency · `-->` sequential dependency · `-.->` alternative approach · `---` complements

```mermaid
flowchart TD
    %% ── TYPE classes (node fill = element type) ─────────────────────────────
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef fix         fill:#dc2626,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef perf        fill:#ea580c,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef security    fill:#7f1d1d,color:#fff
    classDef refactor    fill:#0f766e,color:#fff
    classDef migration   fill:#4338ca,color:#fff
    classDef testing     fill:#a16207,color:#fff
    classDef docs        fill:#15803d,color:#fff
    classDef integration fill:#9d174d,color:#fff
    %% ── STATUS classes (node border = implementation status) ─────────────────
    classDef done        stroke:#16a34a,stroke-width:4px
    classDef active      stroke:#d97706,stroke-width:4px
    classDef planned     stroke:#64748b,stroke-width:2px
    classDef blocked     stroke:#dc2626,stroke-width:3px
    classDef hold        stroke:#9333ea,stroke-width:3px

    S0["§0 Current State — LoRA trainer · SD3 · ComfyUI · data pipeline"]:::infra:::done

    subgraph IMG["§1 Image Generation"]
        direction TB
        S11["§1.1 Anime Captioning — WD14 + Florence-2 [Quick Win]"]:::feature:::done
        S12["§1.2 v-Prediction / zero-terminal-SNR [Research]"]:::research:::planned
        S13["§1.3 LyCORIS — LoCon / LoHa / LoKr [Research]"]:::research:::planned
        S14["§1.4 ControlNet + IP-Adapter — ComfyUI workflows"]:::integration:::planned
        S15["§1.5 FLUX.1 dev — FP8/GGUF secondary [Research]"]:::research:::planned
        S16["§1.6 Anime Upscaling — Real-ESRGAN / 4x-AnimeSharp [Quick Win]"]:::augment:::planned
    end

    subgraph VID["§2 Video & GIF Generation"]
        direction TB
        S21["§2.1 AnimateDiff — motion modules [Research]"]:::research:::planned
        S22["§2.2 ToonCrafter — inbetweening [Research]"]:::feature:::planned
        S23["§2.3 Foundation Video — Wan2.1 / SVD [Long-term]"]:::research:::planned
        S24["§2.4 Consistency + Control — IP-Adapter / ControlNet for video"]:::augment:::planned
    end

    S3["§3 Fine-Tuning Pipeline — Video → Character LoRA"]:::feature:::planned
    S4["§4 Hardware-Aware Deployment — 3090 Ti / 4080 profiles"]:::infra:::planned

    subgraph LEG["Legend"]
        direction LR
        LA["✅ Complete"]:::infra:::done
        LB["New Feature"]:::feature:::planned
        LC["Research"]:::research:::planned
        LD["Augmentation"]:::augment:::planned
        LE["Integration"]:::integration:::planned
        LF["Infrastructure"]:::infra:::planned
    end

    %% Critical blocking deps (existing infra unlocks all new work)
    S0 ==> S11
    S0 ==> S14
    S0 ==> S16

    %% Training pipeline: captioning + objectives + algos all feed §3
    S11 --> S3
    S12 --> S3
    S13 --> S3

    %% ControlNet infra reused by FLUX wrapper
    S14 --> S15

    %% Upscaling complements generation (shared module)
    S16 --- S14

    %% Image gen control infra enables video workflows
    S14 --> S21
    S14 --> S24

    %% AnimateDiff and ToonCrafter: complementary video features
    S21 --- S22

    %% Foundation video models come after AnimateDiff is solid
    S21 --> S23

    %% Video control wraps foundation models
    S24 --> S23

    %% Trained models unlock hardware deployment profiles
    S3 ==> S4
```

*Reading guide: follow `==>` arrows (thick) for must-have blockers — the §0 current-state infrastructure is the root. Thin `-->` arrows show feature dependencies within phases. Dashed `-.->` marks alternative approaches. Lines without arrowheads (`---`) mark complementary features that share code or benefit from co-deployment.*

---

## How to Use This Document

Each section: current state in the codebase → pain point → options with trade-offs → recommendation. Tags: **[Quick Win]** (<1 day), **[Research]** (prototype first), **[Long-term]** (depends on external data/infra). Phased execution sequence is summarised at the end and mirrored into the [Master Roadmap](../ROADMAP.md).

---

## 0. Current State (what already exists)

The repository already ships a substantial generation stack — this roadmap **extends** it, it is not greenfield.

| Component | Location | State |
|---|---|---|
| **LoRA trainer** | `backend/src/models/lora_diffusion.py` (`LoRATuner`) | SDXL dual-encoder; default base `OnomaAIResearch/Illustrious-XL-v2.0`; SDXL micro-conditioning. Working. |
| **DreamBooth / full FT** | `backend/src/models/full_finetune.py` | Present. |
| **SD3.5 generation** | `backend/src/models/sd3_wrapper.py` (`SD3Wrapper`) | Text-to-image; ControlNet TODO. |
| **ComfyUI integration** | `backend/src/models/comfy_manager.py`, `gui/.../comfy_generate_tab.py` | Server lifecycle + browser launch. |
| **GAN / R3GAN** | `gan.py`, `gan_wrapper.py`, R3GAN tabs | Present. |
| **Data pipeline** | `backend/src/models/data/` — `video_frame_extractor.py`, `captioner.py`, `lora_dataset.py`, `augmentations.py` | Frame extraction, captioning, dataset, augmentation. |
| **GUI tabs** | `gui/src/tabs/models/{gen,train}/` — LoRA train, SD3 gen, ComfyUI gen, GAN/R3GAN | Present. |
| **Training diagnostics** | `backend/src/models/hooks/`, `modules/`, `subnets/` | Hooks present. |

**Gap analysis vs. consolidated research:** the base-model default is right (Illustrious-XL), the trainer is SDXL-aware, the data pipeline exists. Missing: anime-native captioning (WD14/Florence-2), LyCORIS variants, v-prediction/zero-terminal-SNR support, IP-Adapter/ControlNet wiring in the gen tabs, FLUX support, and the entire video-generation capability (AnimateDiff/ToonCrafter).

---

## 1. Image Generation

### 1.1 Anime-native captioning (WD14 + Florence-2) [Quick Win] — done (2026-07-27, issue #32)

**Current:** `captioner.py` already had a full `HybridCaptioner` (WD14 booru tags + optional Florence-2 sentence + trigger token + per-base-model quality prefix) wired into `anime_training_pipeline.py`'s captioning stage — this predates issue #32 and the roadmap text above was stale (it described this as unimplemented). What issue #32 actually found and fixed:

- **A (WD14 primary, confidence-thresholded):** already implemented via an inline `WD14Tagger` class in `captioner.py` (general_thresh=0.35 default, matches WD14 convention) — but it duplicated, rather than reused, the shared `backend/src/models/wrappers/wd_tagger_wrapper.py::WDTaggerWrapper` from `new_features.md` §4.4 (Auto-Tagger), which was itself fully built but never called from anywhere (dormant). Fixed: added a `_wd_tag()` adapter in `captioner.py` so `HybridCaptioner.wd` now accepts either backend, and wired `WDTaggerWrapper` in as the pipeline's fallback default (`anime_training_pipeline.py::_run_captioning` now uses the legacy local-path `WD14Tagger` only if an explicit `data.captioning.wd14_onnx` file exists, otherwise falls back to `WDTaggerWrapper`, which auto-downloads `SmilingWolf/wd-v1-4-convnext-tagger-v2` from Hugging Face Hub — repo existence and exact filenames [`model.onnx`, `selected_tags.csv`] verified reachable). This is the "implement once, use in both tagging and training" sharing the original recommendation called for. Also found and fixed a real bug while wiring this in: `WDTaggerWrapper`'s `_CATEGORY_NAMES` mapped WD category `9` to `"copyright"`; the real `selected_tags.csv` uses category `9` for the 4-way **rating** group (general/sensitive/questionable/explicit), not copyright — fixed, with a test update.
- **C (trigger token per character):** already wired via `data.trigger_word` in the Hydra training config — the same field `LoRADatasetV2`/`BucketSample` use to identify "the character" being trained, confirmed as the natural existing mechanism (no new input added).
- **B (Florence-2 augmentation):** already implemented as a plain natural-language sentence appended after the booru tags (`"<tags>. <sentence>"`) when `florence` is supplied and `use_florence2=true` — no new work needed here.
- **Additive prose mode:** added `HybridCaptioner(caption_mode="booru"|"prose")` (default `"booru"`, fully backward compatible) so pure VLM-prose captioning stays available as an explicit option per the issue's requirement, rather than only reachable by omitting `wd`.
- **Not verified end-to-end:** `onnxruntime` is not installed in the project's `.venv` (only `huggingface_hub` is), so no real ONNX inference was run against the downloaded model in this session — the HF repo/filenames were confirmed reachable via the HF API, and all logic was verified with mocked ONNX sessions in `backend/test/models/test_captioner.py` (new) and `backend/test/models/test_wd_tagger_wrapper.py` (updated for the category fix). Installing `onnxruntime` and running a real image through `WDTaggerWrapper.tag()` is the remaining step to fully close this out.

**Recommendation (original):** A+C now (booru tags + trigger token), B as augmentation. Shared with the Auto-Tagger feature — implement once, use in both tagging and training. **Status:** A+B+C all in place; see above for what changed and what's still unverified.

### 1.2 v-Prediction / zero-terminal-SNR support [Research]

**Pain point:** NoobAI-vpred and Illustrious-vpred bases use v-prediction + zero-terminal-SNR, which fixes brightness/contrast bias and improves anime's flat saturated palettes and dark scenes. `LoRATuner` must match the base's objective (eps vs v-pred) or output degrades.

**Recommendation:** Detect the base's prediction type and switch the training/sampling objective accordingly. Add v-pred + ztSNR to `LoRATuner` and the SD3/SDXL samplers.

### 1.3 LyCORIS variants (LoCon / LoHa / LoKr) — GUI exposure DONE 2026-07-27

**Pain point:** Standard LoRA captures the character but not the conv-layer style; LoCon (`dim 16 / conv 8`) is preferred for style-bound characters, LoHa/LoKr for tiny datasets.

**Done:** the "integrate the lycoris library into LoRATuner" half of this
bullet's recommendation was **already fully implemented** before this
session touched it — `LoRATunerV2` (`backend/src/models/tuning/
lo_ra_tuner_v2.py`) already dispatches `cfg.method == "lycoris"` to
`lycoris.kohya.create_network()` with `lora`/`locon`/`loha`/`lokr`/`dylora`
algorithms, and a `lycoris_locon.yaml` Hydra preset already existed under
`backend/config/training/`. **The actual gap was "expose in the LoRA train
tab"** — the GUI's `LoRATrainTab` only ever instantiated the *legacy*
`LoRATuner` (V1, no LyCORIS support at all; V2 is documented in its own
module docstring as the "adds LyCORIS support" successor) and never called
into `LoRATunerV2` or the Hydra pipeline in any way.

- **Added two missing presets**: `lycoris_loha.yaml` and `lycoris_lokr.yaml`
  (only `lycoris_locon.yaml` existed), each with algorithm-appropriate
  dims/epochs per this bullet's own "LoHa/LoKr for tiny datasets" framing
  (smaller nominal rank, more epochs to compensate for fewer trainable
  parameters on small datasets).
- **Found and fixed a pre-existing, unrelated bug that blocked this
  entirely**: `anime_training_pipeline.py` (the orchestrator `LoRATunerV2`
  needs — dataset bucketing, tuner construction, training loop) had two
  broken imports left over from a prior code reorganization
  (`backend.src.models.full_finetune` and `backend.src.models.
  lora_diffusion`, neither of which exist anymore — the real paths are
  under `backend.src.models.tuning.*`). This meant `python -m
  backend.dispatcher command=train` has been completely broken for *any*
  training run, LyCORIS or standard, since that reorganization — nobody
  had noticed because nothing actually invoked this pipeline. Fixed both
  imports; verified via a real Hydra `--cfg job` dry-run composition for
  all four training presets (`lora_4080`, `lycoris_locon/loha/lokr`).
- **GUI**: new "Training Engine" dropdown in `LoRATrainTab`
  (`gui/src/tabs/models/delta/lora_train_tab.py`) — "Standard (LoRA)"
  keeps the existing legacy `LoRATuner` path completely unchanged (zero
  risk to current behavior); the three LyCORIS options launch `python -m
  backend.dispatcher command=train training=lycoris_<algo> model.model_id=
  ... data.images_dir=... data.trigger_word=... output_dir=...` as a
  subprocess (reusing the existing, now-fixed pipeline end-to-end rather
  than re-implementing dataset/tuner construction inline), streaming
  output to the status label and supporting Cancel via `proc.terminate()`.
- **Tests**: 10 new cases in `gui/test/models/test_lora_train_tab_lycoris.py`
  covering the engine dropdown defaults, the standard path staying on the
  legacy tuner, correct Hydra CLI command construction for all three
  algorithms, and success/error/cancel signal handling — all passing.
  `--cfg job` dry-run composition verified separately (real Hydra, not
  mocked) since the actual training run itself needs GPU/VRAM not
  available in this environment.

### 1.4 ControlNet + IP-Adapter in generation tabs — Phase A ✅ Done (2026-08-05, issue #35)

**Pain point:** Pose/composition control (ControlNet OpenPose/depth/lineart) and character/style reference (IP-Adapter) are the two highest-leverage controllability features, currently TODO in `sd3_wrapper` and absent from the SDXL gen path.

**Options.** **A** Route control through ComfyUI workflows (the gen tab already launches ComfyUI) — fastest, most flexible. **B** Native diffusers ControlNet/IP-Adapter pipelines in the wrappers — tighter GUI integration, more code.

**Recommendation:** A first (ship a curated set of ComfyUI workflow JSONs: txt2img, pose-control, reference-transfer, upscale), B for the native SDXL gen tab later.

**Shipped as:** Phase A only (Option A above), matching the issue's own two-part
scope ("Phase A quick win now, Phase B native diffusers integration later").

- **Investigation first — the ComfyUI integration was less built-out than
  this section implied.** `ComfyUIManager` (`backend/src/models/core/
  comfy_manager.py`) only started/stopped the ComfyUI server subprocess and
  exposed its URL for the user to open in a system browser; there was no
  in-app mechanism to submit a workflow JSON, override its parameters, or
  supply an extra image via ComfyUI's HTTP API. `ComfyUITab` (`gui/src/
  tabs/models/gen/comfy_generate_tab.py`) was correspondingly just a
  "Start/Stop server + Open in Browser + log viewer" panel — the user was
  expected to build/run workflows entirely inside ComfyUI's own web UI. §1.1
  and §1.6 (captioning, upscaling) don't depend on this mechanism at all, so
  this doesn't call the rest of the roadmap's "done" claims into question —
  it's specific to the ComfyUI launch path this item needed.
- **Smallest correct extension, per the task's own fallback plan:** added
  four methods to `ComfyUIManager` — `load_workflow()` (load a curated
  template JSON by bare name or path), `apply_overrides()` (a generic
  `{node_id: {input_key: value}}` merge into a workflow's node inputs,
  returning a deep copy), `upload_image()` (multipart POST to ComfyUI's
  `/upload/image`, returning the server-side filename a `LoadImage` node
  can reference), and `queue_workflow()` (POST to `/prompt`, returning the
  `prompt_id`). This is the "generic extra image inputs parameter dict
  passed through to workflow JSON node overrides" mechanism the task
  anticipated, not a larger refactor.
- **Curated workflow JSON templates** (`configs/comfy_workflows/`,
  ComfyUI's own "API format" node-graph shape — the same format already
  used by the pre-existing personal reference pipeline at `configs/
  workflow_api.json`): `controlnet_generate.json` (`CheckpointLoaderSimple`
  → `ControlNetLoader` + `LoadImage` → `ControlNetApplyAdvanced` →
  `KSampler` → `VAEDecode` → `SaveImage`) and `ipadapter_generate.json`
  (`CLIPVisionLoader` + `IPAdapterModelLoader` + `LoadImage` →
  `IPAdapterAdvanced` → `KSampler` → `VAEDecode` → `SaveImage`, mirroring
  the IP-Adapter node pattern already proven working in `configs/
  workflow_api.json`). The ControlNet template deliberately takes an
  **already-preprocessed** control image (a pose skeleton / depth map /
  canny edge map), not a raw photo — turning a raw photo into one of those
  requires the `comfyui_controlnet_aux` custom node pack, which is not part
  of core ComfyUI and out of this item's scope; the three "pose / depth /
  canny" GUI modes share this one template and differ only in which
  ControlNet checkpoint + pre-processed control image the user supplies.
- **GUI wiring** — `ComfyUITab` gained a "ControlNet / IP-Adapter Workflow"
  panel: a mode dropdown (Pose / Depth / Canny / IP-Adapter Reference, each
  auto-filling the matching default checkpoint filename and image-field
  label), base-checkpoint and extra-checkpoint text fields, a control/
  reference image file picker, positive/negative prompt fields, and a
  "Queue Workflow" button. Clicking it uploads the selected image via
  `ComfyUIManager.upload_image()`, builds the node-override dict, and
  submits via `ComfyUIManager.queue_workflow()` on a background thread,
  logging the returned `prompt_id` (or any error) to the existing log
  panel — the same "background thread + Qt signal back to the log view"
  pattern the server-start path already used.
- **Model checkpoints — same "user provides, app doesn't download"
  convention already established by `configs/parameters.json`/`workflow_api
  .json`:** the GUI's checkpoint fields are free-text with tooltips naming
  the required `ComfyUI/models/{checkpoints,controlnet,ipadapter}/`
  subfolder; nothing in this change downloads or validates model weights,
  per this task's explicit constraint.
- **Tests:** `backend/test/models/test_comfy_manager.py` (12 tests —
  template loading, override merging incl. non-mutation and unknown-node
  handling, mocked-urllib `upload_image`/`queue_workflow` incl. the HTTP
  error path) and `gui/test/models/test_comfy_generate_tab.py` (16 tests —
  mode-switch field wiring, `build_workflow()` node-override correctness
  for every mode, the queue handler's guard rails and happy/error paths,
  file-picker browse/cancel). All 28 new tests pass; the pre-existing 107
  `gui/test/models/` and full `backend/test/models/` suites (150 tests
  total) still pass — no regressions.
- **Manual smoke test:** loaded both curated templates and applied real
  node overrides through the actual (non-mocked) `ComfyUIManager.
  load_workflow()`/`apply_overrides()` path outside pytest, confirming both
  parse as valid ComfyUI API-format graphs (every node has `class_type` +
  `inputs`) and that overrides land on the right nodes.
- **Not done here (explicitly out of scope):** actually running generation
  against a live ComfyUI server with real ControlNet/IP-Adapter weights —
  no such weights exist in this environment and downloading multi-GB
  checkpoints was an explicit non-goal; raw-photo-to-control-map
  preprocessing (needs `comfyui_controlnet_aux`, a custom node pack not
  installed here); Phase B (native diffusers `StableDiffusion3ControlNetPipeline`
  / `IPAdapterMixin` wiring into `sd3_wrapper.py` and `SD3GenerateTab`) —
  tracked separately per this section's own Option B / CG-3 (Quality) split,
  and `SD3GenerateTab`'s existing `controlnet_ckpt`/`controlnet_cond_image`
  fields are still unwired stubs, untouched by this change.

### 1.5 FLUX.1 [dev] secondary support [Research]

**Pain point:** FLUX is the quality king for prompt adherence/text but a poor *primary* anime base (VRAM-heavy, slow to train, thin anime ecosystem). Worth supporting as a secondary model for stylised realism.

**Recommendation:** Add a FLUX wrapper with FP8/GGUF Q8 quantisation for 16 GB; rectified-flow sampler; keep it clearly secondary in the UI.

### 1.6 Anime upscaling stage [Quick Win] — shared wrapper DONE 2026-07-27

**Pain point:** Generated images and stitched panoramas both want anime-aware SR.

**Done:** `ESRGANWrapper` (`backend/src/models/wrappers/esrgan_wrapper.py`) — a
tiled Real-ESRGAN anime_6B upscaler, the shared reusable primitive this
item asked for. **Correction to this bullet's own claim**: `animation/
super_res.py` does not exist anywhere in the codebase (confirmed by a
repo-wide search before writing anything) — there was no super-resolution
module to "unify" with; this wrapper is a new module, not a merge of two
existing ones.

- **Architecture**: a self-contained RRDBNet (Residual-in-Residual Dense
  Block Network, the Real-ESRGAN generator) in plain `torch`, rather than
  the `basicsr`/`realesrgan` PyPI packages (not installed in this
  project's `.venv`; deliberately not added — `basicsr` carries a large,
  fragile dependency tree with known compatibility breaks against newer
  torchvision). Matches this project's established pattern for BiRefNet/
  ToonOut: load raw weights into a hand-written architecture.
- **Weights verified, not guessed**: downloaded the real
  `RealESRGAN_x4plus_anime_6B.pth` checkpoint from its HF Hub mirror and
  inspected the actual state dict before writing the architecture —
  confirmed 6 RRDB blocks, `num_feat=64`, weights wrapped under a
  `params_ema` key (Real-ESRGAN's own convention). Two independent HF Hub
  mirrors (`ximso/...`, `gemasai/...`) wired as primary/fallback, same
  pattern as `birefnet_wrapper.py`.
- **Tiled inference**: large images processed in overlapping tiles
  (`tile_size=400`, `tile_pad=10` defaults) to bound VRAM/RAM use, matching
  upstream Real-ESRGAN's own approach. Verified quantitatively against a
  non-tiled full-pass on the same image: mean abs pixel diff 0.76/255
  under production tile settings, with boundary-adjacent pixels showing
  the expected (and upstream-documented) minor tiling-seam effect — not a
  bug, an accepted trade-off of the tiling approach itself.
- **Verified end-to-end with real downloaded weights** (not just "loads
  without erroring"): loaded the actual anime_6B checkpoint and ran both
  the non-tiled and tiled code paths on synthetic images, confirming
  correct 4x output shape and dtype in both cases.
- **Tests**: `backend/test/models/test_esrgan_wrapper.py`, 16 tests —
  architecture shape checks (locking the real checkpoint's 6-block/
  64-feature structure), primary/fallback/failure load() paths, tiled vs
  non-tiled shape correctness (including a non-tile-size-multiple
  remainder case), file-path convenience wrapper, unload lifecycle. Uses
  randomly-initialized small weights for CI speed (no network dependency
  in the committed suite) — the real-weights end-to-end run above was done
  manually, documented here rather than asserted in CI, same convention as
  this session's WD14 tagger work.
- **Not done here** (separate, larger follow-on items, out of this
  Quick-Win's scope): wiring `ESRGANWrapper` into the generation tabs' GUI,
  and into an actual ASP super-resolution pipeline stage (which itself
  doesn't exist yet — see the correction above). This item delivers the
  shared primitive module only.

---

## 2. Video & GIF Generation {: #2-video-gif-generation }

### 2.1 AnimateDiff motion modules [Research]

**Pain point:** No video generation today. AnimateDiff is the mature, controllable path — a motion module dropped into any SDXL/Illustrious anime checkpoint plus the user's trained character LoRA produces short clips/GIFs without retraining the base.

**Options.** **A** Via ComfyUI (AnimateDiff-Evolved nodes) — minimal new code, leverages existing ComfyUI integration. **B** Native diffusers `AnimateDiffPipeline` — GUI-integrated, more code/VRAM management.

**Recommendation:** A first (curated AnimateDiff workflow JSONs + motion-LoRA presets for pan/zoom). Add context-window/prompt-travel presets for longer clips on 16 GB.

### 2.2 ToonCrafter inbetweening [Research]

**Pain point:** Generative inbetweening between two anime key-frames (large motion gap), and the dual-use ghost-fill for the ASP composite (occlusion completion).

**Recommendation:** ToonCrafter wrapper (shared with ASP `animation/anim_fill.py`); GIF-from-two-keyframes tab feature. Cross-links the generation and stitching pipelines.

### 2.3 Foundation video models (Wan2.1 / SVD) [Long-term]

**Pain point:** Longer, more coherent clips than AnimateDiff need DiT-class foundation models (Wan2.1, SVD), at 24 GB+ or with offloading.

**Recommendation:** 3090 Ti-only feature behind a VRAM gate; Wan2.1 via `diffusion-pipe`; defer until AnimateDiff path is solid.

### 2.4 Consistency & control (IP-Adapter / ControlNet for video)

**Recommendation:** Reuse §1.4 control infrastructure across frames — IP-Adapter for character consistency, ControlNet (OpenPose/depth) for kinematic control, both inside the AnimateDiff ComfyUI workflows.

---

## 3. Fine-Tuning Pipeline (4K video → character LoRA) {: #3-fine-tuning-pipeline-4k-video-character-lora }

This is the flagship cross-cutting capability — it reuses Image-Toolkit's FFmpeg extraction, similarity/dedup, and database.

**Current:** `video_frame_extractor.py`, `lora_dataset.py`, `augmentations.py`, `LoRATuner`, `full_finetune.py` all exist.

**Gaps / steps:**
1. **Scene-aware extraction** — PySceneDetect integration on top of `video_frame_extractor` (deinterlaced, full-res, exact-PTS).
2. **Curation & dedup** — reuse `SimilarityFinder` (phash/SSIM) to drop blur/dupes; pose/expression balancing.
3. **Captioning** — §1.1 WD14 + Florence-2 + trigger-token schema.
4. **Per-GPU training configs** — TOML presets: `illustrious_character_4080_16gb.toml`, `noobai_vpred_3090ti_24gb.toml`.
5. **Diagnostics** — loss/grad-norm curves, periodic validation-image sampling, weight-norm viz (extend `hooks/`).
6. **DeepSpeed ZeRO-2** for full-checkpoint FT on the 3090 Ti.

**Recommendation:** Wire these into a single "Train Character LoRA from Video" guided flow in the LoRA train tab — the concrete user-facing feature that distinguishes Image-Toolkit (it already has the video + database halves).

---

## 4. Hardware-Aware Deployment

| GPU | Profile | Capabilities |
|---|---|---|
| **RTX 3090 Ti (24 GB)** | Full-fidelity desktop | Full 1024² batch 2–4 LoRA; DreamBooth; full-FT (ZeRO-2); Wan2.1; AnimateDiff long clips. |
| **RTX 4080 (16 GB)** | Constrained desktop | 1024² batch 1–2 + grad-checkpoint LoRA; FLUX FP8/GGUF; AnimateDiff with context windows. |
| **RTX 4080 mobile (12 GB)** | Constrained laptop | 1024² batch 1 + grad-checkpoint; fp8 everything; short AnimateDiff only. |

Env managed via `uv`. VRAM gating in the UI (disable features that won't fit the detected GPU).

---

## Phased Execution Sequence

| Phase | Items | Effort |
|---|---|---|
| **CG-1 (Quick Wins)** | 1.1 WD14+Florence-2 captioning · 1.6 shared anime upscaler · 1.4A ComfyUI control workflows | days |
| **CG-2 (Core)** | 3.x video→LoRA guided flow · 1.3 LyCORIS · 2.1A AnimateDiff via ComfyUI | 1–2 wk/item |
| **CG-3 (Quality)** | 1.2 v-pred/ztSNR · 2.2 ToonCrafter inbetween · 1.4B native ControlNet/IP-Adapter | 1–2 wk/item |
| **CG-4 (Advanced)** | 1.5 FLUX secondary · 2.3 Wan2.1/SVD foundation video · DeepSpeed full-FT | research |

Dependencies: CG-1 captioning unblocks CG-2 training quality; CG-1 upscaler shared with ASP; 2.2 ToonCrafter shared with ASP ghost-fill (`animation/anim_fill.py`). The video→LoRA flow (3.x) is the highest-value differentiator and should lead CG-2.

---

## Effort × Impact Matrix {: #effort--impact-matrix }

*Effort* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks or research prototype
*Impact* — **Low**: marginal · **Medium**: noticeable quality/UX improvement · **High**: major capability unlock · **Very High**: differentiating feature unavailable in comparable tools

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | — | §1.6 shared anime upscaler (unifies gen + ASP upscale path) | §1.1 WD14+Florence-2 captioning · §1.4A ComfyUI control workflows (curated JSONs) | — |
| **Medium (1d–1w)** | — | §1.5 FLUX.1 FP8 secondary support | §1.2 v-pred/zero-terminal-SNR · §1.3 LyCORIS (LoCon/LoHa/LoKr) · §2.1A AnimateDiff via ComfyUI · §2.2 ToonCrafter inbetweening | §3.x Video→LoRA guided flow (scene extract + curate + caption + train) |
| **High (1–2w)** | — | §2.3 Wan2.1/SVD foundation video (3090 Ti only) | §1.4B native ControlNet/IP-Adapter in SDXL gen tab | §2.4 IP-Adapter + ControlNet video consistency |
| **Very High (2w+)** | — | — | §3.6 DeepSpeed ZeRO-2 full-checkpoint FT | §3.x full video→LoRA pipeline (end-to-end trained character from 4K source) |

---

## Document History

*Created 2026-06-03. Research basis: **[`research/Image_Generation_Research.md`](../research/Image_Generation_Research.md)** (merges all 5 prior generation reports). Scope: local anime image generation, character fine-tuning, and video/GIF generation on RTX 3090 Ti (24 GB) and RTX 4080 (16/12 GB).*
