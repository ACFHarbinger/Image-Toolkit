# GIF resample speed: shared ideas report (2026-10-30)

Tracking issue: #1147 (`lanczos3-dering` speed), parent #1123. Roadmap: `docs/moon/roadmaps/new_features.md` §4.22.
Test case: `/home/pkhunter/Downloads/Data/Wallpapers/Other/video_filename_1118717ms_1211710ms.gif`
(326 MB, 720x400, 2232 frames).

## How this report works

1. **Phase 0, Claude:** writes the first ideas below (done).
2. **Phase 1, every agent:** investigates the codebase and the state of the art on the web, then writes its own
   ideas **in its own section** (§5). Offer **several options per goal** with trade-offs; do not collapse to one
   answer. Harbinger will choose.
3. **Phase 2, Claude and Harbinger:** a final pass. Claude asks questions, Harbinger answers and may ask back,
   until every ambiguity is cleared. Answers go in the Q&A log (§7) and the decisions in the Decision log (§8).
4. **Phase 3:** the decisions become the implementation roadmap (§9) and issues. No implementation of an
   option before it is decided, except throwaway prototypes kept out of the repo.

### Rules for contributors

- **Edit only your own section.** Rebase before committing; one small commit per update. Never rewrite another
  author's text. If you disagree with something, add a reply under your own name in §6.
- **Evidence over assertion.** Every claim is marked **[M]** measured by you (give the command, input, hardware,
  numbers), **[C]** cited (paper/repo URL, with what it actually says), or **[H]** hypothesis (untested). Say which.
- **Codebase first, then the web.** Read the real code (`middleware/src/services/media/gif_upscale/`,
  `gui/src/helpers/core/sampler_worker.py`) before proposing. Cite `file:line`.
- **Options format** (use for every optimization goal):
  `Goal` / `Option` / `How` / `Expected gain` / `Cost and risk` / `Equivalence to current output` / `Evidence tag`.
- **Resource rules** (`AGENTS.md`): profiling a few frames is a small check and allowed. Full-corpus runs and
  anything that processes the whole 326 MB GIF go through Codex with Harbinger's go-ahead, one at a time. GPU
  prototypes take a GPU lease and tell the bus first. Scratch files go under `~/Downloads/Data/Tests/`.
- **Prototypes stay out of the repo.** Put them in your scratch area and quote the code in your section if needed.
- **Output equivalence matters.** State for each option whether the output is bit-identical, within float
  rounding, perceptually equivalent, or intentionally different, and how you checked.

## 1. What we know (facts, with how they were obtained)

- **[M]** CPU `lanczos3-dering`, one frame 480x270 to 960x540: 0.14 s; plain Lanczos3: 0.07 s. At 720x400 to
  1440x800 on random RGBA data: 0.28 s per frame (Claude, `_resize.resize_separable`, this machine).
- **[M]** cProfile of the 480x270 case: `_clamp_rgb_to_neighborhood` is about 65% of the dering run, mostly
  `np.take` and masked `np.minimum`/`np.maximum` in `_reduce_horizontal`.
- **[M]** Torch on the GPU (RTX 3090 Ti), dense `Wy @ premul @ Wx^T` plus a batched masked min/max clamp, batch of 32
  frames at 720x400 to 1440x800: 0.0034 s per frame (about 80x), peak 4.3 GB, max abs diff vs CPU 6.6e-5
  (issue #1147 comment). This is the **scale step only**.
- **[M]** On the 326 MB GIF, 2x, `lanczos3-dering`, cancel after 8 s: still in the palette-sampling pass at decode
  frame 1129 of 2232, peak RSS 738 MB. So before any scaling starts, about half the clip has been decoded.
- **[C, code]** `resize_separable` loops frames serially; `_axis_plan` (kernel evaluation, normalization, index
  tables) is rebuilt per frame inside `_separable` although every frame has the same size
  (`classical/_resize.py`).
- **[C, code]** The streaming path in `pipeline.py` (`_resample_gif_stream`) is used when
  `frames * w * h * 16 > 256 MiB`. It first makes a palette from about 16 sampled frames scaled with the chosen
  algorithm, then re-decodes the clip, scaling and writing one frame at a time.
- **[C, code]** `iter_gif_frames` returns a full-canvas RGBA copy per frame via Pillow
  (`np.asarray(image.convert("RGBA")).copy()`), so partial-frame deltas in the file are not exploited.
- **[C, code]** `SamplerWorker` runs several files on a `ThreadPoolExecutor` (up to 8) but a single file is one
  serial job; there is no intra-file parallelism option.
- **Unknown, must be measured before optimizing:** the split of wall time across **decode, palette sampling,
  scale, index/dither, GIF write** on the real file. Everything below is conditional on that.

## 2. Goals

| ID | Goal |
|---|---|
| T1 | Cut wall time of one big GIF end to end (decode to write), not just the scale step. |
| T2 | Make the scale step itself fast on CPU with no GPU. |
| T3 | Use the GPU when one is present, with a safe CPU fallback. |
| T4 | Use all CPU cores for a single request (an explicit, user-visible parameter). |
| T5 | Keep peak memory flat for any clip length; stay cancellable at frame granularity. |
| T6 | Keep output equivalent to today's within a stated tolerance (or document the difference). |

## 3. Claude's ideas (Phase 0)

Each idea lists options. Tags: **[M]** measured, **[H]** hypothesis.

### A. Measure first: a stage profiler for the whole pipeline (T1)

- **Option A1.** Add timing to `resample_gif` stages (decode, palette pass, scale, index/dither, write) behind a
  debug flag, and print a table per run. Cheap; unblocks every other decision. **[H]** that scale is not the only
  big cost: the palette pass decodes about half the clip and quantizer/dither/LZW are CPU Python/NumPy.
- **Option A2.** Profile on a 100-frame slice of the real GIF instead of the whole file, so it is a small check
  rather than a full run.

### B. Fix the algorithmic waste in the CPU scale step (T2)

- **Option B1, taps once per clip.** Compute `_axis_plan` once and reuse for every frame. **[H]** small but free;
  output bit-identical.
- **Option B2, sliding-window min/max for the dering clamp.** Replace the per-tap gather by a separable
  van Herk / `cv2.erode`+`cv2.dilate` style min/max over the source, then one gather by `floor(src_pos)`.
  Roughly O(pixels) instead of O(taps x pixels). **[H]** about 2 to 3x on the clamp. Risk: border and
  invalid-tap windows must match exactly. Equivalence: bit-identical if done right.
- **Option B3, skip alpha work on opaque frames.** Filter RGB only when alpha is all 1 and skip premultiply
  and unpremultiply. **[H]** about 25 percent of the work; output identical.
- **Option B4, dense-matrix form on CPU.** `Wy @ img @ Wx^T` with BLAS (OpenBLAS/MKL) instead of tap gathers; for a
  6-tap kernel the matrices are banded, so a banded or block form avoids wasted flops. **[H]** needs measuring;
  may beat `np.take` loops several times.
- **Option B5, native kernel.** A C++ separable resample with the clamp fused, built into the existing `backend`
  pybind11/OpenMP extension (already part of the build). Fixed-point or float, SIMD friendly. **[H]** the best
  CPU-only result; highest build and maintenance cost.
- **Option B6, integer or half-precision pipeline.** Work in uint8/uint16 fixed point (as libvips/Pillow-SIMD do)
  instead of float32. **[H]** big memory-bandwidth win; output differs by rounding, so it is "within 1 level"
  rather than identical.

### C. Multi-core for a single request (T4)

- **Option C1, `workers` parameter, frame-parallel.** A new param (for example `workers=auto|N`) on the resample
  request. Split the clip into frame chunks, scale in a process pool (processes avoid the GIL for the
  Python parts, and `np.take` only partly releases it), reassemble in order for the writer. Bounded in-flight
  queue keeps memory flat. **[H]** near-linear to core count for the scale step.
- **Option C2, thread pool with a native kernel.** If B5 is chosen, the kernel releases the GIL and threads are
  enough; no pickling of frames between processes.
- **Option C3, split one frame across cores** (row bands) for very large frames and few frames. Tile with halo
  rows. Only worth it when frame count is small.
- **Cancel semantics:** pools must honor the existing `ResampleCancelled` and terminate workers promptly.

### D. GPU (T3)

- **Option D1, torch matmul resample + batched clamp** (the prototype above). Frame batches sized from free VRAM;
  GPU lease; CPU fallback. **[M]** 80x on the scale step.
- **Option D2, CuPy/NPP or a custom CUDA/Triton kernel** fusing premultiply, resample, clamp, unpremultiply into
  one pass; fewer memory trips than torch ops. **[H]** extra 2 to 4x over D1, but a new dependency or build.
- **Option D3, OpenCV CUDA** (`cv2.cuda`) if the wheel has it; usually it does not, and its Lanczos is the 8-tap
  Lanczos4, not Lanczos3. **[H]** probably not viable.
- **Overlap pipeline:** decode and index/encode on CPU threads while the GPU scales (bounded queues), or the GPU
  will idle behind the slowest CPU stage (see E, F).
- **Fallback chain:** GPU, then native CPU, then NumPy; the choice is surfaced to the user, never silent about
  quality (the algorithm itself must not change).

### E. Remove the palette pre-pass cost (T1, T5)

- **Option E1, parallel decode of the sample frames only.** Seek is not possible in GIF (LZW is sequential), but
  the sample positions can be decoded by a separate fast decoder pass or while the main pass runs.
- **Option E2, palette from the downscaled or unscaled source.** Quantize a palette from the *unscaled* sampled
  frames (cheap) instead of scaling 16 frames with the chosen algorithm first. **[H]** small quality change.
- **Option E3, one-pass adaptive palette.** Start with a palette built from the first N frames and extend or
  refine as frames stream, or run the quantizer on the first pass's already scaled frames. Avoids re-decoding the
  whole clip twice. **[H]** removes one full decode pass; needs a check that late scenes keep their colors.
- **Option E4, reuse the source GIF's own (global or local) palettes** mapped through the resize. **[H]** fast,
  often fine for GIFs that came from video, poor when the source palette was already crushed.

### F. Faster decode and encode (T1)

- **Option F1, exploit GIF's own deltas.** GIFs from video are mostly partial frames. Decode the raw sub-rectangle
  and the disposal method, scale only the changed region (with the resample's support margin), and composite onto
  the previous scaled canvas. **[H]** potentially large (many frames change a small area), but exactness near the
  region edges needs care and the dering clamp must see the same neighborhood.
- **Option F2, skip duplicate or near-duplicate frames.** Hash frames; reuse a scaled result for exact duplicates
  (common in held frames and screen recordings). **[H]**
- **Option F3, a faster decoder than Pillow's composite per frame,** for example giflib/libvips/ffmpeg/PyAV or
  `gifsicle --unoptimize`. **[H]**
- **Option F4, index and dither on GPU or in native code.** The nearest-palette lookup and ordered dither are
  per-pixel and trivially parallel. **[H]**
- **Option F5, native LZW writer** (the current `IndexedGifWriter`'s cost is **unknown**, measure it).

### G. Pipeline structure (T1, T5)

- **Option G1, producer/consumer pipeline** (decode thread, scale stage, encode thread) with bounded queues,
  works for CPU, process-pool and GPU variants.
- **Option G2, chunked two-level parallelism:** split the clip into N independent segments with a shared palette,
  scale and encode each segment in its own worker, concatenate the GIF streams. **[H]** scales to all cores,
  but needs a segment-safe frame disposal/loop header handling.

### H. Research directions worth a look (for agents to evaluate)

- Fast approximations of Lanczos: look-up-table kernels, polyphase filters, Halide-scheduled separable resamplers
  (Halide/Apache TVM), Highway/SIMD resampling in libvips and Pillow-SIMD, Intel IPP resize.
- Edge-preserving fast upscalers with the same "no ringing" goal: guided or bilateral filter-based, anti-ringing
  Lanczos variants used by mpv/ffmpeg `zscale`, and learned lightweight upscalers (SPAN/Compact style) as a
  *quality-and-speed* alternative on GPU.
- Temporal methods: reuse of motion-compensated or unchanged regions across frames.
- Anything newer from 2024 to 2026 on video super-resolution acceleration is relevant mainly to the neural
  backends, not to this classical path; keep it separate unless it applies.

## 4. Open questions Claude already has (to settle in the final pass)

1. Must the new path be **bit-identical** to the current output, or is "within 1/255" acceptable?
2. Is a **GPU-only** result acceptable as the default when a GPU is present, or must CPU and GPU agree exactly?
3. Is it acceptable to **add a native C++ kernel** to the existing `backend` extension (extra build surface)?
4. Should `workers` be a **user-visible setting** (per request in the Sampler UI), a global setting, or both?
5. For palette quality: is a **slightly different palette** (E2 to E4) acceptable if it removes a full pass?
6. Is **delta-region scaling** (F1) in scope given the exactness risk, or too risky for a first release?
7. What is the **target wall time** for the 326 MB test GIF, and on which hardware (this 3090 Ti box only)?

## 5. Agent sections (Phase 1: each agent writes only in its own section)

> Template for each agent: **Investigated** (codebase files and external sources read) / **Measurements** /
> **Options** (options format above) / **Recommendation, with reasons and what would change your mind** /
> **Questions for Harbinger**.

### 5.1 Grok-Core (decode, IO, pipeline)

_(not written yet)_

### 5.2 Grok-Cls1 / Grok-Cls2 (classical kernels)

_(not written yet)_

### 5.3 Grok-Enc (palette, dither, GIF writer)

_(not written yet)_

### 5.4 Grok-Eval (evaluation and metrics, equivalence checks)

_(not written yet)_

### 5.5 Grok-Down (downscale suite)

_(not written yet)_

### 5.6 Other Grok agents (GPU, native kernels, research survey)

_(not written yet)_

### 5.7 Codex (review, benchmark runs when authorized)

_(not written yet)_

## 6. Replies and disagreements

_(Add a dated reply under your own name; do not edit other sections.)_

## 7. Q&A log (Phase 2, Claude and Harbinger)

| # | Question | Asked by | Answer | Answered by | Date |
|---|---|---|---|---|---|
| 1 | Must the new path be bit-identical to the current output, or is "within 1/255" acceptable? | Claude | Approximate is acceptable. | Harbinger | 2026-10-30 |
| 2 | Is a GPU result that differs from the CPU one by rounding acceptable as the default? | Claude | Yes. | Harbinger | 2026-10-30 |
| 3 | May we add a native C++ kernel to the existing `backend` extension? | Claude | Yes. | Harbinger | 2026-10-30 |
| 4 | Should `workers` be per request, global, or both? | Claude | Global setting. | Harbinger | 2026-10-30 |
| 5 | Is a slightly different palette acceptable if it removes a whole decode pass? | Claude | Yes, but it must be a setting. | Harbinger | 2026-10-30 |
| 6 | Is delta-region scaling in scope given the exactness risk? | Claude | Yes, but any high-exactness-risk optimization must be a setting or parameter. | Harbinger | 2026-10-30 |
| 7 | Target wall time for the 326 MB GIF, and on which hardware? | Claude | This machine only; expects "a couple of minutes". | Harbinger | 2026-10-30 |
| 8 | "A couple of minutes" is the whole job, decode to written file, for 2232 frames at 2x with `lanczos3-dering`? Roughly 120 to 180 s, so about 50 to 80 ms per frame end to end. | Claude | _(open)_ | | |
| 9 | Should the settings be grouped as one quality/speed mode (for example `exact`, `balanced`, `fast`) with the individual switches under an advanced section, or only individual switches? | Claude | _(open)_ | | |
| 10 | `workers` global default: `auto` (all cores minus one) or a fixed fraction? Should the GUI stay responsive by default (leave cores free)? | Claude | _(open)_ | | |
| 11 | When a GPU is present, should the GPU path be the automatic default, with a global setting to force CPU? And a cap on how much VRAM one job may take (default)? | Claude | _(open)_ | | |
| 12 | The native C++ kernel needs the `backend` extension built. If it is missing, fall back to NumPy with a visible warning, or refuse the job? | Claude | _(open)_ | | |
| 13 | Should the app show which path ran (GPU / native / NumPy, palette mode, delta mode) in the finish message so results are explainable? | Claude | _(open)_ | | |
|

## 8. Decision log

| # | Decision | Options considered | Reason | Decided by | Date |
|---|---|---|---|---|---|
| D1 | Output may be approximate (not bit-identical). Each option still states its tolerance and how it was checked. | Q1 | Speed matters more than bit-exactness. | Harbinger | 2026-10-30 |
| D2 | GPU may be the default when present, with rounding differences vs CPU accepted. | Q2 | Large measured gain. | Harbinger | 2026-10-30 |
| D3 | A native C++ kernel in `backend` is allowed. | Q3 | Best CPU-only result. | Harbinger | 2026-10-30 |
| D4 | `workers` is a global setting (not per request). | Q4 | Simpler UI. | Harbinger | 2026-10-30 |
| D5 | A reduced-pass palette is allowed, controlled by a setting. | Q5 | Removes a decode pass; changes colors slightly. | Harbinger | 2026-10-30 |
| D6 | Delta-region scaling and any other high-exactness-risk optimization is in scope, but gated behind a setting or parameter; the safe path stays available. | Q6 | Keep a trustworthy fallback. | Harbinger | 2026-10-30 |
| D7 | Performance target: about 2 minutes for the 326 MB test GIF on this machine (pending Q8 for exact scope). | Q7 | Defines "fast enough". | Harbinger | 2026-10-30 |
|

## 9. Final implementation roadmap

_(Written after the decisions: ordered tasks, owners, issues, acceptance numbers.)_
