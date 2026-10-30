# GIF upscaling/downscaling — Grok swarm plan (2026-10-30)

Author: Claude. Audience: a swarm of Grok agents plus Codex (runs heavy suites) and Harbinger (go-ahead).
Supersedes the single-algorithm approach in commits `3c7fa2d19` / `0b845fdbc`.

Tracking issue: #1123 (milestone "GIF Upscaling Suite"). Roadmap: `docs/moon/roadmaps/new_features.md` §4.22.

## Decisions (Harbinger, 2026-10-30)

1. **Bundle everything, no license gating.** This is a private tool. Every backend in the catalogue ships, including
   APISR (academic-use-only) and gifski/libimagequant (AGPL-3 / GPL-3). T-LIC no longer blocks anything: it only
   *records* each license in the registry and docs, with one note: these choices make the app non-redistributable, so
   public release would need a re-audit.
2. **Weights: on-demand download is the default, and a user setting chooses the policy.** Setting
   `gif_upscale.weights_policy`: `on_demand` (default) | `prefetch_all` | `offline` (use only weights already in the
   cache; never touch the network). SHA-256 verified either way.
3. **GIF only for now.** APNG / animated WebP / MP4 output, plus still-image and video input, are recorded as
   **optional roadmap entries**, not built in this effort.

## 0. Why this exists

`_resample_gif` in `middleware/src/services/media/subtabs.py` resizes each frame with Pillow
(`lanczos|bicubic|bilinear|nearest`) and re-saves via Pillow's GIF writer. Lanczos and bicubic are fixed kernels:
they cannot create detail, they ring on edges, and on low-res sources they read as pixelated. The user wants the
best available algorithms, split into **realistic** and **anime-style** content, **neural and non-neural**.

Two defects are independent of the resize algorithm and must be fixed regardless:
1. **Lossy GIF write.** Each RGBA frame is re-quantized to 256 colors by Pillow with default dithering and no
   shared palette. Upscaled gradients band and frames shimmer. A better upscaler is wasted behind a poor encoder.
2. **Transparency / disposal.** Everything is flattened to full RGBA frames with `disposal=2`, so partial-frame and
   transparent GIFs are mishandled and files bloat.

## 1. Algorithm catalogue (research summary)

Confidence marks: **[V]** verified from a primary source this session, **[S]** secondary/blog only, **[?]** license or
detail NOT verified. Every `[?]` becomes a blocking task (T-LIC) before that backend ships.

### 1.1 Realistic content

| Tier | Algorithm | Kind | Notes |
|---|---|---|---|
| A | **Real-ESRGAN** `x4plus`, `x2plus`, `realesr-general-x4v3` | neural GAN, per frame | Baseline. Repo already has `ESRGANWrapper` (`middleware/src/models/wrappers/esrgan_wrapper.py`, RRDBNet). [V in repo] |
| A | **HAT / DAT / DRCT** (transformer SISR) | neural, per frame | Higher fidelity than ESRGAN-family; heavier. NTIRE 2025 x4 entries built on DRCT/SwinFIR/HAT; hybrids won. [S] |
| A | **SwinIR / MambaIRv2** | neural, per frame | MambaIRv2 paired with TSD-SR won the NTIRE 2025 perceptual track. [S] |
| B | **OSEDiff / TSD-SR / SeedVR2-image** | one-step diffusion, per frame | Best perceptual quality for real-world degradation; hallucination risk, needs a fidelity guard. [S] |
| C | **SeedVR2** (3B/7B) | one-step diffusion **video** SR, ICLR 2026 | Temporal consistency across frames; reported ~1 H100 for 720p. Likely too heavy for a 24 GB 3090 Ti at larger sizes. License reported Apache-2.0 [S][?]. Attribution conflicts across blogs (ByteDance vs other) — verify. |
| C | **FlashVSR v1.1** | one-step diffusion streaming VSR | ~17 FPS at 768x1408 on A100 per authors. Needs Block-Sparse Attention (custom compile, tuned for A100/A800/H200). License not stated in README. [V code/weights exist][?] |
| C | **DOVE** (CogVideoX-based one-step VSR) | video SR | Close to SeedVR2 on UDM10 in a 2026 paper (arXiv 2601.20308). Verify weights availability and license. [S][?] |
| C | **STAR, RealViformer (ECCV 2024), InfVSR** | video SR | Lower priority; STAR scored below DOVE/SeedVR2 in the same table. Investigation only. |
| D | **Non-neural**: Lanczos3 with **deringing** (clamp / anti-ringing), **Catmull-Rom**, **bicubic-sharper**, **EWA/Jinc** (mpv-style), **FSR 1.0 EASU+RCAS**, **NEDI / edge-directed interpolation**, unsharp + guided-filter detail pass | classical | Fallback when no GPU/weights; downscale path (see 1.3). |

### 1.2 Anime-style content

| Tier | Algorithm | Kind | Notes |
|---|---|---|---|
| A | **Real-CUGAN** (bilibili/ailab) 2x/3x/4x, denoise levels incl. conservative | neural, waifu2x-compatible CUNet | Fast, strong on line art. Official code `bilibili/ailab/Real-CUGAN`. Weights license NOT stated in results. [S][?] |
| A | **APISR** (CVPR 2024) 2x/4x | neural, still-image anime SR | Strong on compressed/real anime frames; official repo says **academic use only** — this is a **blocker for shipping bundled weights**. [V] |
| A | **Real-ESRGAN anime-6B** (`RealESRGAN_x4plus_anime_6B`) and **`realesr-animevideov3`** | neural | Already referenced in repo as `ANIME_6B_MODEL` / `ANIME_6B_MODEL_FALLBACK`. [V in repo] |
| A | **waifu2x** (CUNet / upconv_7 anime) | neural | Classic, line-art safe, denoise baked in. Via NCNN-Vulkan or PyTorch. [S] |
| B | **SPAN / Compact (SRVGGNetCompact) fine-tunes** | lightweight neural | For CPU / low-VRAM and quick previews. [S] |
| B | **AnimeSR** (video, NeurIPS 2022) | neural video SR | Anime-specific temporal model; investigate. [?] |
| D | **Anime4K** (GLSL-derived: restore / upscale CNN variants) | non-neural-ish shader pipeline | Cheap, deterministic, no weights. Reimplement the CPU/NumPy or Torch port; check license. [S][?] |
| D | **Pixel-art scalers**: Scale2x/EPX/Scale3x, **xBR/xBRZ**, **hqx**, **nearest + integer** | classical | For sprite / pixel GIFs. Never run a GAN on pixel art. |
| D | **Vectorization-style upscale** (edge-preserving: guided/bilateral + sharpen, flat-region snap) | classical | Experimental; keeps flat color fills crisp. |

### 1.3 Downscaling (separate problem)

Downscaling needs **anti-aliasing**, not detail synthesis. Candidates: **area / box (INTER_AREA)**, **Lanczos with
proper pre-filter**, **gamma-correct (linear-light) resampling**, **SSIM-driven downscaling (Öztireli & Gross)**,
**mpv `ssim_downscaler`-style**, **Catmull-Rom for photo**, **nearest/integer for pixel art**. Resize in linear light,
not gamma space, and premultiply alpha.

### 1.4 GIF encoding (the half everyone forgets)

- **gifski / libimagequant** = global-palette + cross-frame palettes + temporal dithering; thousands of colors per
  frame via palette tricks. gifski is **AGPL-3** [V]; `libimagequant` is dual-licensed (GPL-3 / commercial) [?].
  Per decision 1 these are allowed (private tool): offer **gifski (binary, if installed) and libimagequant** as the
  top encoder, with the own-implementation encoder below as the always-available fallback.
- Own-implementation encoder (always available): **Pillow `quantize(method=LIBIMAGEQUANT)` only if the build includes it** (check),
  **median-cut / octree / k-means (own implementation)**, **Floyd–Steinberg + blue-noise ordered dithering**, and a
  **temporally stable palette** (quantize once on the union of all frames, then dither with a fixed noise mask
  to stop shimmer).
- GIF is capped at 256 colors and is the real quality ceiling. APNG / animated WebP / MP4 output is deferred to the
  roadmap (decision 3), but `encode.py` must keep the container behind an interface so adding them is cheap.

## 2. Architecture

Everything behind one interface so the frontend lists backends dynamically.

```
middleware/src/services/media/gif_upscale/
  __init__.py
  registry.py        # AlgorithmSpec(id, family, content: realistic|anime|pixel|any, kind: neural|classical,
                     #   supports_scale: set[float], supports_downscale: bool, needs_gpu: bool,
                     #   vram_mb_estimate, license, weights_sha256, available() -> (bool, reason))
  base.py            # FrameUpscaler protocol: upscale(frames: list[np.ndarray RGBA f32], scale, opts) -> list[...]
                     #   VideoUpscaler protocol: takes the whole clip (temporal models)
  io.py              # GIF decode: composited RGBA frames, durations, loop, disposal, transparency index
  encode.py          # palette + dither + write; the encoder strategies from 1.4
  temporal.py        # flicker reduction: optical-flow-guided blend (RAFT-small / Farneback), per-pixel median
  tiling.py          # tile + overlap + feather blend for any model; OOM backoff
  classical/         # lanczos_deringed.py, catmull_rom.py, ewa.py, fsr1.py, edi.py, scale2x.py, xbr.py, anime4k.py
  neural/            # realesrgan.py, realcugan.py, waifu2x.py, apisr.py, hat.py, swinir.py, osediff.py,
                     # seedvr2.py, flashvsr.py, dove.py, animesr.py
  downscale/         # area.py, linear_light.py, ssim_downscale.py
  auto.py            # content classifier (anime vs photo vs pixel-art) -> recommended backend
```

- Reuse `ESRGANWrapper` — do **not** fork it; wrap it.
- Take a GPU lease via `middleware/src/core/gpu_lease_arbiter.py` and register VRAM estimates in
  `gpu_vram_estimate.py` / `gpu_vram_calibration.py`. Never allocate outside a lease.
- `subtabs.resample` keeps its signature. New params: `algorithm` (registry id), `content`
  (`auto|realistic|anime|pixel`), `denoise`, `dither`, `palette` (`global|per_frame|temporal`), `temporal`
  (`off|flow|model`), `output` (`gif|apng|webp`). Unknown or unavailable algorithm ⇒ **explicit error with the
  reason from `available()`**, never a silent fallback to Lanczos (that would hide the very problem being fixed).
- Frontend: `frontend/src/views/ConvertSubtabs.tsx` populates the algorithm `<select>` from a new
  `list_resample_algorithms` service call; group by Realistic / Anime / Pixel / Classical, and grey out
  unavailable ones with the reason.
- Contracts: regenerate combined contracts per repo workflow after the service surface changes.

## 3. Swarm structure

Each agent works in its **own worktree on its own branch** under `~/Downloads/Data/Tests/` (never `main`; see top of
`AGENTS.md`). All coordination goes through the bus (`.agent/bus/<date>.md`). Agents land **small commits**, never
force-push, and never touch another lane's files.

### Wave 0 — foundation (sequential; blocks everything)
| ID | Owner | Deliverable |
|---|---|---|
| G0-1 (#1124) | Grok-Core | `registry.py`, `base.py`, `io.py` (lossless decode: composited frames + durations + loop + transparency), `tiling.py`. Unit tests with synthetic GIFs. |
| G0-2 (#1125) | Grok-Enc | `encode.py`: global/temporal palette + dithering + disposal/transparency handling; **replace** the Pillow path in `_resample_gif`. Regression tests: gradient GIF has no banding beyond a threshold (measure with ΔE / SSIM against source), transparent GIF round-trips alpha. |
| G0-3 (#1126) | Grok-Eval | Evaluation harness (`tools/eval/gif_sr/`): corpus builder + metrics (PSNR/SSIM for synthetic degrade→restore, **LPIPS, DISTS, NIQE/MUSIQ** for no-reference, **flicker metric** = temporal warping error), HTML contact-sheet report. Corpus lives under `~/Downloads/Data/Tests/gif_sr_corpus/`, never in the repo. Runs go through **Codex** (see §5). |
| G0-4 (#1127) | Grok-Lic | **T-LIC (record only, blocks nothing):** read the actual LICENSE for every `[?]` row (SeedVR2, FlashVSR, DOVE, Real-CUGAN weights, Anime4K, AnimeSR, libimagequant, APISR, gifski), record in `docs/` + the registry `license` field, and add the weights-policy setting (`on_demand` / `prefetch_all` / `offline`) with the cache and SHA-256 verification. |

### Wave 1 — classical (parallel, no weights, CPU-safe) — fastest to ship
| ID | Owner | Content |
|---|---|---|
| G1-A (#1128) | Grok-Cls1 | Lanczos3+deringing, Catmull-Rom, bicubic-sharper, EWA/Jinc. |
| G1-B (#1129) | Grok-Cls2 | FSR1 EASU+RCAS, NEDI/edge-directed, guided-filter detail pass. |
| G1-C (#1130) | Grok-Pix | Scale2x/3x, EPX, xBRZ, hqx, integer-nearest, pixel-art detector. |
| G1-D (#1131) | Grok-Down | Downscale suite 1.3: area, linear-light, SSIM downscale, alpha-premultiplied. |
| G1-E (#1132) | Grok-A4K | Anime4K port. |

### Wave 2 — neural per-frame (parallel; each behind a GPU lease)
| ID | Owner | Content |
|---|---|---|
| G2-A (#1133) | Grok-ESR | Real-ESRGAN x2/x4/general-v3 + anime-6B + animevideov3 via existing `ESRGANWrapper`. |
| G2-B (#1134) | Grok-CUGAN | Real-CUGAN 2x/3x/4x with denoise levels. |
| G2-C (#1135) | Grok-W2X | waifu2x (CUNet/upconv_7) via PyTorch or NCNN. |
| G2-D (#1136) | Grok-TF | HAT / DAT / DRCT / SwinIR / MambaIRv2 (transformer lane; pick two, benchmark first). |
| G2-E (#1137) | Grok-APISR | APISR 2x/4x. |
| G2-F (#1138) | Grok-Lite | SPAN / Compact fine-tunes for CPU / low VRAM + live preview. |

### Wave 3 — diffusion and video-aware (serial GPU; start only after Wave 2 baselines exist)
| ID | Owner | Content |
|---|---|---|
| G3-A (#1139) | Grok-Diff | OSEDiff / TSD-SR one-step diffusion per frame + **fidelity guard** (reject frames whose LPIPS to the bicubic reference exceeds a bound; blend toward it). |
| G3-B (#1140) | Grok-VSR | SeedVR2 (3B), FlashVSR v1.1, DOVE as `VideoUpscaler`s. Tile in time and space; verify they fit 24 GB (the dev box is an RTX 3090 Ti, 24 GB) or mark `needs_gpu_vram_mb` so the registry greys them out. |
| G3-C (#1141) | Grok-Anim | AnimeSR video model. |
| G3-D (#1142) | Grok-Flow | `temporal.py`: flow-guided flicker reduction applied *after* any per-frame model; RAFT-small or classical Farneback. Anime needs a gentler setting (hand-drawn frames are held, not smooth). |

### Wave 4 — integration
| ID | Owner | Content |
|---|---|---|
| G4-1 (#1143) | Grok-Auto | `auto.py` content classifier (photo / anime / pixel) + the default recommendation table; tested on the corpus. |
| G4-2 (#1144) | Grok-UI | Frontend selector, grouping, availability reasons, previews, vitest. |
| G4-3 (#1145) | Grok-Docs | `docs/` page: algorithm guide, VRAM table, license table, "which one should I pick". Bus entry. |
| G4-4 (#1146) | Codex | Review all lanes with Bugbot; run the benchmark pass (§5). |

## 4. Acceptance criteria (every backend)

1. Registered with accurate `kind`, `content`, `supports_*`, `vram_mb_estimate`, `license`, `weights_sha256`.
2. `available()` returns a precise reason (missing weights, no CUDA, license gate).
3. Weights follow the `gif_upscale.weights_policy` setting (default `on_demand`, SHA-256 verified, user cache),
   and are never committed (check `.gitignore`; no binaries in git). `offline` never touches the network.
4. Deterministic seed for anything stochastic; tests use tiny synthetic inputs and `tmp_path`.
5. Tiled inference matches untiled output within tolerance (no seams).
6. GIF-specific tests: transparency, partial-frame disposal, variable per-frame duration, loop count, 1-frame GIF,
   odd sizes, very large frame counts (stream, don't hold everything in RAM).
7. Quality gate on the eval corpus: beats Lanczos on **LPIPS/DISTS** for its content class and does not regress the
   flicker metric by more than an agreed bound. Numbers go in the bus entry.
8. `ruff check`, `py_compile`, type check, targeted tests pass. Frontend vitest + `tsc` for UI tasks.
9. Failure is loud: no silent downgrade to Lanczos.

## 5. Resource rules (from `AGENTS.md`, restated because they bite here)

- **No agent other than Codex may run the benchmark/corpus passes or any full suite.** Post the request to the bus
  addressed to Codex; Codex relays to Harbinger and waits for go-ahead. One run at a time.
- Small, targeted checks are fine for any agent: single test file, `-k` selection, `ruff`, `py_compile`.
- Neural inference of even one GIF can saturate the GPU. Wave 2/3 agents **must not run model inference
  concurrently**; take the GPU lease and keep manual test runs to a few frames. Tell the bus before any GPU run.
- Scratch outputs go under `~/Downloads/Data/Tests/`, not the repo.
- Do not background a run and leave it unmonitored.

## 6. Risks / remaining notes

1. **Redistribution.** Bundling academic-only (APISR) and AGPL/GPL (gifski, libimagequant) components makes the app
   private-use only. Re-audit before any public release.
2. **Heavy video models** (SeedVR2, FlashVSR, DOVE) may not fit or run well on a 24 GB card at useful resolutions,
   and FlashVSR needs a custom Block-Sparse Attention build. Ship as "advanced / experimental"; registry greys them
   out when VRAM or the build is missing.
3. **Diffusion hallucination** on realistic GIFs (faces, text): default to the fidelity-guarded blend (G3-A).
4. **GIF's 256-color ceiling** is the final quality limit; other containers are on the roadmap (decision 3).

## 6b. Roadmap-only (optional, not in this effort)

APNG / animated WebP / MP4 output; still-image and video input through the same registry; Real-ESRGAN-style
batch folders. Tracked in `docs/moon/roadmaps/new_features.md` §4.22.

## 7. Suggested order and effort

1. G0-1, G0-2, G0-4 in parallel → merge. (G0-2 alone already fixes the banding bug.)
2. G0-3 harness, then Wave 1 in parallel — ships a real improvement with no weights.
3. Wave 2 in parallel but GPU-serialized; A/B each against Lanczos on the corpus.
4. Wave 3 only if Wave 2 results justify it.
5. Wave 4 integration, review, docs.

## 8. Sources

- SeedVR2: arXiv 2506.05301; DOVE/STAR/OSDEnhancer comparison: arXiv 2601.20308; InfVSR: arXiv 2510.00948
- FlashVSR: github.com/OpenImagingLab/FlashVSR (HF: JunhaoZhuang/FlashVSR-v1.1)
- APISR: arXiv 2403.01598, github.com/Kiteretsu77/APISR (academic-use-only note in README)
- Real-CUGAN: github.com/bilibili/ailab/tree/main/Real-CUGAN
- NTIRE 2025 x4 SR challenge report (DRCT / HAT / MambaIRv2 / TSD-SR); HAT: arXiv 2309.05239
- gifski (AGPL-3, libimagequant-based): github.com/ImageOptim/gifski
