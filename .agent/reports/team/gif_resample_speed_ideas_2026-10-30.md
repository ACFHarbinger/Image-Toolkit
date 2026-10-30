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

Grok, 2026-10-30. Lanczos3-dering only. Palette indexing and LZW are Gemini's §5.8 and Claude's remeasure in §6. I am not restating those as if a faster kernel alone meets D14.

#### Investigated

- `middleware/src/services/media/gif_upscale/classical/_resize.py`. `_separable` builds a fresh `_axis_plan` for both axes on every frame (`_resize.py` around the `x_index, x_weight` lines). `_apply_taps` walks the six Lanczos taps with `np.take` plus multiply-add. `_clamp_rgb_to_neighborhood` then runs `_neighborhood_range`, which is the same tap mask reduced with chunked `np.take` and masked min/max. Premultiply and unpremultiply run on all four channels (`_premultiply`, `_finish`).
- `pipeline.py` `_resample_gif_stream`: one frame is scaled, indexed, and LZW-written before the next frame starts. A scale-only speedup does not overlap with encode.
- Report §1 and §5.8, plus Claude's §6 check of those numbers.
- External: Pillow-SIMD's own resize write-up (AVX2 Lanczos about 4–6× Pillow, and in their older tables about 10× ImageMagick on one AVX2 core) at <https://python-pillow.org/pillow-perf/> and <https://uploadcare.com/blog/the-fastest-production-ready-image-resize/>. libvips `vips_reduce` is a separable Lanczos3 used after a block shrink, streamed in regions (<https://github.com/libvips/libvips/wiki/HOWTO----Image-shrinking>). mpv's `--scale-antiring` is a 0..1 strength on separable scalers, off at 0, and the man page says a non-zero value while downscaling adds aliasing (<https://manpages.ubuntu.com/manpages/resolute/en/man1/mpv.1.html>). FFmpeg `zscale` / libswscale `lanczos` is the same windowed sinc with `param0` taps, not our clamp (FFmpeg scaler docs, <https://ffmpeg.org/ffmpeg-scaler.html>).

#### Measurements

- **[M]** This machine, one thread, `get_algorithm("lanczos3-dering").upscale` on one random RGBA frame, 720×400 → 1440×800, after one warmup call: **0.2917 s**. Pillow `Image.resize(..., LANCZOS)` on the RGB channels of that same frame: **0.0153 s** (no dering, no alpha). Command: a 15-line `python` snippet in the repo venv, `numpy` Generator seed 0. Pillow is about 19× faster than today's full dering path and about 4× faster than the 0.07 s no-dering figure already in §1, but it is not the same operation.
- I did not re-time `_lzw` or `index_frame`. I use Claude's §6 figures below (scale 292 ms, index 7.19 s, LZW 0.42 s, Pillow encode 14.8 ms).

#### Options

**Goal T2. Scale one 720×400 frame to 1440×800 with Lanczos3 and a no-ring clamp, on one CPU thread.**

- **Option Gk-A, cache the axis plan for the clip.**
  - **How.** `_axis_plan` depends only on source size, dest size, support, and kernel. Compute it once per clip (or once per call of `resize_separable` over a frame list) and pass the arrays in. `_separable` currently rebuilds both plans inside the per-frame function.
  - **Expected gain.** **[H]** a few percent of the 0.29 s. The plan is two small index/weight tables (6 taps by dest length). The 0.29 s is the gathers, not `sinc`.
  - **Cost and risk.** Tiny. Must key the cache by size and kernel id so a mixed-size batch cannot reuse the wrong plan.
  - **Equivalence.** Bit-identical.
  - **Evidence.** **[C]** code. **[H]** for the percent.

- **Option Gk-B, exact-window clamp with a sliding min/max, not a gather per tap.**
  - **How.** The valid taps are a short contiguous run in source space (Lanczos3 support 3, so at most six source samples). A separable sliding-window minimum (van Herk, or a small ring buffer along the row) computes the same min/max as today's `_reduce_vertical` / `_reduce_horizontal` without `np.take` of a full destination row per tap.
  - **Expected gain.** **[H]** the clamp is about 65% of 0.29 s (§1), so removing the gather overhead is on the order of 2× on the clamp and roughly 1.4–1.8× on the whole scale step. Not 6×. Gemini's §5.8 `Gem-T2a` already measured a related idea (sgemm plus `cv2.erode`/`dilate` and `cv2.remap`) at 48.96 ms, 6.0×, with bit-identical `lo`/`hi`. That number is theirs, not mine. A pure sliding window should land between today's 292 ms and that 49 ms, closer to 49 ms if the filter half is also replaced.
  - **Cost and risk.** Border taps that are out of range must stay excluded. A rectangular 6×6 window is not the same as the per-output valid-tap mask. Gemini reports the rectangular clamp matched `lo`/`hi` on their frame. I have not repeated that.
  - **Equivalence.** Bit-identical bounds if the mask matches. Rectangular window is "same on the frames where Gemini checked", otherwise it can clamp a pixel the current mask never read. Put the rectangular form behind `balanced` (D9, D22's mode split). Keep today's mask for `exact`.
  - **Evidence.** **[C]** §1 cProfile and §5.8. **[H]** for a NumPy sliding window I have not timed.

- **Option Gk-C, Pillow-SIMD Lanczos for the filter, our clamp kept only in `exact`.**
  - **How.** Call Pillow-SIMD `resize` (Lanczos, support 3) for RGB, and for alpha unless Gk-E skips it. In `balanced`/`fast`, either skip the clamp or apply mpv-style `--scale-antiring` as a strength in 0..1: blend the filtered pixel toward the local min/max instead of a hard clip. In `exact`, run the current clamp after the Pillow resize.
  - **Expected gain.** **[M]** stock Pillow Lanczos is 15.3 ms versus 292 ms for our full path, on RGB only. **[C]** Pillow-SIMD's published AVX2 tables are about 4–6× that Pillow again for Lanczos (<https://python-pillow.org/pillow-perf/>). **[H]** `balanced` with no clamp is about 15 ms/frame here, about 33 s of scale for 2232 frames. `exact` still pays the clamp, so it stays near a large fraction of 0.29 s unless Gk-B or Gk-D lands.
  - **Cost and risk.** Pillow-SIMD is a fork, not the Pillow already in the venv. Shipping it means a wheel build (D3 allows native code; this is a third-party wheel instead). Pillow's edge treatment and uint8 rounding differ from our float32 kernel. Uploadcare measured that calculating Lanczos coefficients inside the pixel loop dominates, which is what their SIMD kernel avoids. Our `_axis_plan` already hoists coefficients, so the remaining gap is the gather loop, not `sin`.
  - **Equivalence.** `balanced`: intentionally different (Pillow uint8 Lanczos, weaker or no dering). Claude's §6 note says Pillow's uint8 path can miss by up to 38/255 versus float Lanczos. That is outside 1/255. `exact`: within float rounding only if we clamp our own float kernel, not Pillow's bytes. Do not call Pillow output "exact".
  - **Evidence.** **[M]** 15.3 ms vs 0.2917 s. **[C]** Pillow-SIMD tables and §6's 38/255 note.

- **Option Gk-D, two-phase 2× kernel, AVX2, in `backend`.**
  - **How.** The test case is exactly 2×. Under `_tap_table`, output positions fall on two phases. A native separable kernel with those two weight rows, float32, fused clamp, processes a row band and releases the GIL. `workers` (D4, D10, default 1) maps to OpenMP or a thread pool over row bands or over frames. If `backend` is missing, run Gk-A/Gk-B and say so (D12). Finish message names the path (D13).
  - **Expected gain.** **[H]** Pillow-SIMD's Lanczos bandwidth on one AVX2 core is tens of megapixels per second. A 720×400 frame is 0.29 MP. At even 20 MP/s that is about 15 ms, in the same band as stock Pillow and well under 49 ms. Times 2232 frames is about 30–110 s of scale, inside the 2-minute stage budget on one core if the kernel is actually in that band. This is not a measurement of our kernel.
  - **Cost and risk.** New C++ in `backend`, plus a test that the two phases match `_axis_plan` for 2× and that a non-2× scale still uses the general path. Highest maintenance of the CPU options. Worth it only if `exact` must stay on our kernel. If `balanced` may call Pillow, Gk-C is less code.
  - **Equivalence.** Within float32 rounding of today's kernel for 2× when the phases match. Non-2× unchanged.
  - **Evidence.** **[H]**, grounded by **[C]** Pillow-SIMD Lanczos rates and **[M]** our 0.29 s Python baseline.

- **Option Gk-E, skip alpha when the frame is opaque.**
  - **How.** If `alpha` is identically 1, filter three channels and write alpha = 1. Video-derived GIFs are usually opaque after compositing.
  - **Expected gain.** **[H]** about one quarter of the tap loop, roughly 70 ms off the 292 ms if the fourth channel is a full quarter. Premultiply becomes a no-op, which also simplifies the clamp (it currently clamps premultiplied RGB).
  - **Cost and risk.** A single transparent pixel must take the slow path. Detection is one reduction.
  - **Equivalence.** Bit-identical for fully opaque frames. Transparent frames unchanged.
  - **Evidence.** **[H]**. **[C]** four-channel loop in `_apply_taps`.

**Goal T3. Scale on the GPU when one is present.**

- **Option Gk-F, keep the measured torch batch as the GPU scale stage.**
  - **How.** §1 already measured dense `Wy @ premul @ Wx^T` plus a batched clamp at 0.0034 s/frame for 32 frames of this size, peak 4.3 GB, max abs diff 6.6e-5. Run that under the existing GPU lease. Batch size from free VRAM at start, shrink if another job asks (D11, D16). CPU fallback is Gk-D or Gk-C, and the finish line says which (D12, D13).
  - **Expected gain.** **[C]** from §1: about 80× on the scale step versus the 0.28 s CPU figure. 2232 frames × 3.4 ms is about 8 s of scale, far under the 2-minute stage budget. The job still waits on index and LZW unless those move too (§5.8).
  - **Cost and risk.** Torch is already a dependency. VRAM spikes if the batch is "all free VRAM" and the clamp materializes `lo`/`hi` for the whole batch. Cap the batch by the 4.3 GB / 32-frame measurement, not by a guess.
  - **Equivalence.** Within about 1e-4 absolute on the §1 check. D2 accepts that as the default when a GPU is present.
  - **Evidence.** **[C]** §1. I did not rerun the GPU prototype.

- **Option Gk-G, mpv antiring strength instead of a hard clamp, GPU or CPU.**
  - **How.** A parameter `antiring` in 0..1. 0 is pure Lanczos. 1 is today's hard clip to the local min/max. Values in between lerp. mpv documents this for separable scalers and warns that non-zero antiring while downscaling adds aliasing.
  - **Expected gain.** **[H]** little speed versus a hard clamp if both still need the min/max. The win is a quality knob (D1, D9), not a faster inner loop. Skipping the clamp entirely (`antiring=0`, `fast` mode) drops the 65% clamp.
  - **Cost and risk.** Another setting. Downscale plus antiring can alias. Default `balanced` should not turn it on for downscale.
  - **Equivalence.** Intentionally different unless the strength is 1 and the window matches.
  - **Evidence.** **[C]** mpv man page `--scale-antiring`. **[H]** for speed.

**Goal T4. One request, several cores. `workers` stays default 1 (D10).**

- **Option Gk-H, frame pool only after the no-GPU window.**
  - **How.** Do not spawn workers unless the user set `workers` or accepted a count in the D15 window. Each worker scales a frame with a shared read-only axis plan (Gk-A). The writer stays on one thread. In-flight frames capped (two or three per worker) so RSS stays flat (T5).
  - **Expected gain.** **[H]** near-linear in the scale step up to memory bandwidth. At 49 ms/frame native and 8 workers, scale for 2232 frames is about 15 s. At today's 292 ms and 8 workers, about 80 s. Either is inside a 2-minute scale stage. Index at 7 s/frame does not shrink because of this option.
  - **Cost and risk.** GIL: `np.take` in `_apply_taps` holds Python between taps, so threads on the current NumPy path will disappoint. Processes cost copies. Native Gk-D with the GIL released is the one that makes threads work (Claude's C2). Warn when batch multi-core is also on (D10).
  - **Equivalence.** Bit-identical if the plan and kernel match.
  - **Evidence.** **[H]**. **[C]** `SamplerWorker` thread pool is per file, not per frame (`gui/src/helpers/core/sampler_worker.py`).

#### Recommendation

Do not spend the next implementation pass on another NumPy rewrite of `_apply_taps`. Gemini's measured 49 ms scale and Claude's confirmation put a careful CPU scale step at about 109 s for 2232 frames, which already fits D14. The streaming loop is still about 7.2 s of `index_frame` plus 0.42 s of `_lzw` per frame (Claude §6). Fix those first, with D22's 7-bit LUT for `balanced`/`fast` and Pillow's C encoder for the write.

For Lanczos itself, the order I would accept:

1. **Gk-F** when a GPU is present. Scale stage becomes seconds. Tolerance is the 6.6e-5 already measured.
2. **Gk-C in `balanced`/`fast`** on CPU (Pillow Lanczos, no hard clamp), and **Gk-B's exact mask in `exact`**. Pillow-SIMD only if we are willing to own that wheel. Otherwise **Gk-D** for `exact` on CPU, because stock Pillow is the wrong bytes for `exact` (up to 38/255 in §6).
3. **Gk-A** and **Gk-E** in every path. They are small and bit-identical.
4. **Gk-H** only as the D15 window's worker count, default 1, and only after the kernel releases the GIL.

What would change this: a profile, after the LUT and Pillow LZW exist, that still shows scale above about 2 minutes. Then Gk-D moves ahead of palette work. Also change it if a real frame from the 326 MB GIF shows Gemini's rectangular `lo`/`hi` is not bit-identical. Then `balanced` cannot claim their 6× number without a visible difference.

#### Questions for Harbinger

- **Gk-Q1.** For `balanced`, is Pillow's uint8 Lanczos (no dering) acceptable, given §6's up-to-38/255 gap, or must `balanced` stay on the float kernel plus a cheaper clamp (Gk-B / Gemini's 49 ms path)?
- **Gk-Q2.** Should a non-2× scale keep today's NumPy kernel forever, with Gk-D only for the 2× test case? The wallpaper job is 2×. Arbitrary Sampler dimensions are not.

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

### 5.8 Gemini (Lanczos & end-to-end streaming pipeline)

#### Investigated

- **Codebase:**
  - `middleware/src/services/media/gif_upscale/classical/_resize.py` (`resize_separable:86`, `_axis_plan:196`, `_apply_taps:213`, `_separable:236`, `_neighborhood_range:277`, `_reduce_vertical:314`, `_reduce_horizontal:341`)
  - `middleware/src/services/media/gif_upscale/classical/lanczos_deringed.py` (`upscale:15`)
  - `middleware/src/services/media/gif_upscale/classical/kernels.py` (`resize_rgba:19`)
  - `middleware/src/services/media/gif_upscale/pipeline.py` (`_resample_gif_stream:86`, `_palette_samples:147`, `_scale_frames:210`)
  - `middleware/src/services/media/gif_upscale/encode.py` (`IndexedGifWriter.add_frame:58`, `index_frame:76`, `_lzw:90`, `_indexes:257`)
  - `middleware/src/services/media/gif_upscale/io.py` (`iter_gif_frames:18`, `composite_disposal:45`)
  - `gui/src/helpers/core/sampler_worker.py` (`SamplerWorker._execute:49`, `_STAGE_TICKS:340`)
- **External sources:**
  - **libvips (`vips_reduceh` / `vips_reducev`) & Highway SIMD:** Separable 1D horizontal/vertical passes using fixed-point coefficients for integer pixels and float/SIMD accumulators, avoiding intermediate full-frame transposes (`https://www.libvips.org/API/current/libvips-resample.html`).
  - **Pillow-SIMD (`libImaging/Resample.c`):** Precomputes polyphase coefficient tables (`_precompute_coeffs`) once per `(src_len, dst_len, support)`, packs horizontal/vertical passes with AVX2/SSE4 `maddubs`/`madd` instructions; note that standard Pillow clips intermediate horizontal results to `uint8 [0, 255]` between passes (`https://github.com/uploadcare/pillow-simd`).
  - **Halide separable schedule (`tile`, `compute_at`, `store_at`, `vectorize`):** Fusing producer (`resize_x`) and consumer (`resize_y` + clamp) at row-strip granularity (`store_at(yo).compute_at(yi)`) keeps intermediate buffers inside L1/L2 cache instead of writing full `dst_h x dst_w` tensors to DRAM multiple times (`https://halide-lang.org/`).
  - **mpv / libplacebo anti-ringing (`--scale-antiring`, `--scale-clamp`):** Orthogonal and polar EWA Lanczos anti-ringing clamps each output pixel toward the local support neighborhood min/max (`lo`, `hi`) or biases negative lobe weights (`https://libplacebo.org/`, `https://mpv.io/manual/stable/#options-scale-antiring`).
  - **FFmpeg `palettegen` / `paletteuse` & Bayer dithering (`libavfilter/vf_paletteuse.c`):** Uses a precomputed 3D RGB lookup table (5- or 6-bit per channel cube + lazy/precomputed cache) with ordered `8x8` Bayer dithering and `diff_mode=rectangle` so per-frame quantization is an $O(1)$ table lookup per pixel rather than an $O(\text{pixels} \times 256)$ brute-force distance scan, and ordered Bayer patterns preserve repeating byte runs for fast LZW compression (`https://ffmpeg.org/ffmpeg-filters.html#paletteuse`, `http://blog.pkh.me/p/21-high-quality-gif-with-ffmpeg.html`).

#### Measurements

All measurements below were taken on this machine (1 to 3 frames of `/home/pkhunter/Downloads/Data/Wallpapers/Other/video_filename_1118717ms_1211710ms.gif`, `720x400 -> 1440x800`, `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 cv2.setNumThreads(1)` unless noted):

- **[M] Hidden bottleneck in `_resample_gif_stream` (`pipeline.py:115-121`):**
  In the streaming loop (`for seen, (frame, duration, _) in enumerate(iter_gif_frames(input_path))`), each frame executes `_one_frame` (`lanczos3-dering`), `index_frame`, and `writer.add_frame` (`_lzw`) **inside the `"scale"` progress stage**. Timing a single `720x400 -> 1440x800` frame across stages reveals:
  - `decode` (`iter_gif_frames` via Pillow): **5.57 ms/frame** (projected 2,232 frames: **12.4 s**)
  - `scale` plain `lanczos3` (`resize_separable`, `dering=False`): **111.21 ms/frame** (**248.2 s**)
  - `scale` `lanczos3-dering` (`resize_separable`, `dering=True`): **294.20 ms/frame** (**656.7 s = 10.9 min**)
  - `index_frame` (`encode.py:257`, `_indexes` chunked `(8192, 256, 3)` float32 distance): **7,052.01 ms/frame (7.05 s/frame -> 15,740 s = 4.37 hours for 2,232 frames!)**
  - `writer.add_frame` (`encode.py:90`, pure-Python byte-by-byte `_lzw` over 1,152,000 pixels): **474.54 ms/frame** (**1,059 s = 17.6 min**)
  - **Key finding:** `index_frame` + `_lzw` account for **96.2% of the per-frame time reported under "Scaling frame N/2232"** (`7.53 s` out of `7.82 s` per frame). Optimizing `lanczos3-dering` alone cannot bring a streaming job under 4.5 hours unless `index_frame` and `_lzw` are fixed alongside it.
- **[M] Exact sliding-window neighborhood clamp (`cv2.erode` + `cv2.dilate` + `cv2.remap` on source RGB):**
  Because `support = 3.0` uses a 6-tap window `offsets = [-2, -1, 0, 1, 2, 3]` (`_resize.py:172`), computing the $6 \times 6$ min/max on the **source** `400x720` RGB image (`cv2.copyMakeBorder` by 1 pixel + `cv2.erode`/`cv2.dilate` with `np.ones((6, 6))`, `anchor=(2, 2)`) takes **3.40 ms**, and gathering to `800x1440` via `cv2.remap(..., cv2.INTER_NEAREST)` takes **10.19 ms** (**13.59 ms total** vs **165.66 ms** in `_neighborhood_range`, a **12.2x speedup**) with **`max_abs_diff = 0.00e+00` (bit-identical float32 `lo`/`hi` bounds)**.
- **[M] 1-thread CPU 2D OpenBLAS `sgemm` separable Lanczos3 + `cv2` clamp:**
  Note that 3D NumPy `Wy @ chw @ Wx` falls back to a slow ufunc loop (**294.8 ms**), whereas calling 2D OpenBLAS `sgemm` per channel (`for c in range(3): out_chw[c] = Wy @ (chw[c] @ Wx)` with precomputed dense `Wy (800, 400)` and `Wx (720, 1440)` on opaque frames) takes **35.72 ms** on 1 CPU thread. Combined with the **13.59 ms** `cv2` clamp, 1-thread CPU `lanczos3-dering` drops from **294.20 ms to 48.96 ms/frame (6.0x faster)**, with **`max_abs_diff = 4.17e-07` in float32** (at most 1/255 rounding diff on 1 pixel out of 3.45M).
- **[M] Why Pillow's `Image.Resampling.LANCZOS` cannot simply replace `_resize.py`:**
  Measured `Image.fromarray(rgb_u8).resize((1440, 800), Image.Resampling.LANCZOS)` takes **28.37 ms/frame** (including `cv2` uint8 dering clamp), but differs from `_resize.py` by up to **38/255 levels** in interior pixels (`mean = 0.55` levels) because Pillow rounds and clips the horizontal pass to `uint8 [0, 255]` before running the vertical pass, clipping negative/positive Lanczos lobe overshoots prematurely.
- **[M] Fast palette indexing (`encode.py:_indexes`) and C GIF LZW encoding (`encode.py:_lzw`):**
  - Exact BLAS identity $\arg\min_p (\frac{1}{2}\|p\|^2 - x \cdot p)$ drops `_indexes` from **6,474 ms to 467.5 ms/frame** (**13.8x**), bit-identical.
  - A 6-bit per channel (`64x64x64 = 262,144` byte) 1D flat LUT (`lut_1d[(r<<12)|(g<<6)|b]`) built once per clip in **104.3 ms** drops `index_frame` (including Bayer dithering) from **7,052 ms to 7.66 ms/frame (920x faster, 17.1 s for 2,232 frames)** with **1.87/255 RGB RMSE**. A 7-bit (`128x128x128 = 2 MiB`) LUT gives <0.8/255 RMSE at the same lookup speed.
  - Delegating frame LZW compression to Pillow's C GIF encoder (`Image.fromarray(fast_idx, mode="P").save(buf, format="GIF")`) takes **18.93 ms/frame** vs **474.54 ms/frame** in pure-Python `_lzw` (**25x faster**, **42.3 s** for 2,232 frames, zero new dependencies).
- **[M] Combined 1-thread CPU prototype (`OPENBLAS_NUM_THREADS=1`, no GPU, no C++ rebuild):**
  `decode (5.57 ms) + scale_dering (48.96 ms) + lut_index (7.66 ms) + c_lzw (18.93 ms) = 81.13 ms/frame` -> **181.1 s (3.0 min total) for 2,232 frames on 1 CPU core**, with every stage well under the 2-minute per-stage budget (`scale = 109.3 s`, `encode = 59.4 s`, `decode = 12.4 s`).

#### Options

##### Goal T2: Make `lanczos3-dering` (and all separable scalers in `_resize.py`) fast on CPU

- **Option Gem-T2a: Precomputed clip plan + 2D OpenBLAS `sgemm` per channel + `cv2.erode`/`dilate`/`remap` clamp + opaque-frame fast path (Pure Python/NumPy/OpenCV).**
  - **How:**
    1. Hoist `_axis_plan(src_w, dst_w, ...)` and `_axis_plan(src_h, dst_h, ...)` out of the per-frame loop so `Wy`, `Wx`, and `cv2.remap` coordinate grids `(map_x, map_y)` are built once per clip.
    2. Check `np.all(frame[..., 3] >= 1.0 - 1e-6)` (or `frame_u8[..., 3].min() == 255` before float conversion); when opaque, skip premultiply, alpha channel filtering, and unpremultiply (25% fewer channels and no division pass).
    3. Run separable filtering via 2D `cblas_sgemm` (`out_chw[c] = Wy @ (chw[c] @ Wx)`) instead of 3D `@` or per-tap `np.take`.
    4. Compute the 6-tap neighborhood min/max on the **source** image via `cv2.erode` and `cv2.dilate` (`6x6` kernel, `anchor=(2, 2)`, `BORDER_REPLICATE` on 1-pixel padded source) and project to `(dst_h, dst_w)` with `cv2.remap(..., cv2.INTER_NEAREST)`. (When downscaling or when any `frac(src_pos) == 0.0` disables the 6th tap, fall back to a 1D separable `erode`/`dilate` with exact active tap width or maskless `np.minimum.reduce` on `x_idx_valid`).
  - **Expected gain:** **6.0x faster** on 1 CPU thread (**294.2 ms -> 48.96 ms/frame**, **109 s** for 2,232 frames).
  - **Cost and risk:** Low (~80 lines in `_resize.py`, uses already-imported `numpy` and `cv2`). Must guard the `cv2.erode`/`dilate` fast path to upscales (`scale >= 1.0`) where the tap window is a uniform $6 \times 6$ block.
  - **Equivalence to current output:** Float32 `max_abs_diff = 4.17e-07` (`lo`/`hi` bounds are bit-identical `0.00e+00`; filter differs only by FMA float32 associativity, $\le 1/255$ on 0.00003% of pixels).
  - **Evidence tag:** **[M]** measured above.

- **Option Gem-T2b: Halide-scheduled fused C++ / AVX2 row-strip kernel in `backend` (`pybind11` + OpenMP).**
  - **How:** Add `backend.resize_lanczos3_dering_batch` in `backend/src/image/`:
    1. Precompute horizontal and vertical 6-tap index/weight tables once.
    2. Follow the Halide `store_at(yo).compute_at(yi)` schedule: Maintain a 6-row ring buffer of horizontally filtered rows (`wide_ring[6][dst_w][C]`) and a 6-row ring buffer of horizontally reduced source min/max (`lo_ring[6][dst_w][3]`, `hi_ring[6][dst_w][3]`) in L1/L2 cache.
    3. As each new source row enters the 6-row window, compute its horizontal 6-tap convolution and 6-tap min/max in one AVX2 pass (`_mm256_fmadd_ps` / `_mm256_min_ps` / `_mm256_max_ps`), then vertically combine the 6 cached rows, clamp `rgb` to `[lo, hi]`, convert to `uint8`, and emit the output row directly.
  - **Expected gain:** **15x to 25x faster** on 1 core (~12–18 ms/frame) and **80x to 150x faster** across 8–16 OpenMP threads (~1.5–3 ms/frame), because it eliminates all full-frame intermediate allocations (`wide`, `tall`, `high`, `vertical_lo`, `vertical_hi`, `lo`, `hi` — currently 7 full-frame float32 buffers per frame) and keeps the working set under 150 KB in L2 cache.
  - **Cost and risk:** Medium (~200 lines of C++ in `backend/src/image/` + `bindings.cpp`; requires `just build::build-base` and falls back to Option Gem-T2a when the `.so` is absent per D12).
  - **Equivalence to current output:** Within float32 rounding (`< 1e-6` float32, $\le 1/255$ uint8).
  - **Evidence tag:** **[C]** Halide row-strip schedule + **[H]** estimated from memory-bandwidth reduction (7 full-frame DRAM round-trips reduced to 1).

- **Option Gem-T2c: Int16 Q14 fixed-point polyphase C++ / SIMD kernel (libvips / Pillow-SIMD style, without intermediate uint8 clipping).**
  - **How:** Convert `uint8` input directly to `int16`, represent normalized 6-tap Lanczos weights in signed `Q2.14` (`int16_t`, sum = `16384`), keep intermediate horizontal pass in **unclamped signed `int16`** (avoiding Pillow's bug of clamping intermediate overshoots to `[0, 255]`), and fuse the `uint8` neighborhood min/max clamp at the end of the vertical pass using `_mm256_madd_epi16` / `_mm256_min_epu8` / `_mm256_max_epu8`. Also skip float32 conversion of decoded frames (`frame.astype(np.float32) / 255.0` in `pipeline.py:116`).
  - **Expected gain:** **25x to 40x faster** on CPU (2x wider SIMD lanes than float32 and half the L1/L2 cache footprint; removes `uint8 -> float32 -> uint8` conversions).
  - **Cost and risk:** Medium-High (requires `uint8` frame interface or fast path in `pipeline.py` so frames aren't converted to `float32` before calling the scaler).
  - **Equivalence to current output:** Within $\pm 1/255$ level vs float32 reference (`Q14` quantization error is $< 2^{-13} \approx 1.2 \times 10^{-4} \ll 1/255$).
  - **Evidence tag:** **[C]** libvips/Pillow-SIMD fixed-point design + **[M]** confirmed Pillow's 38-level error comes only from intermediate `[0, 255]` clipping, not fixed-point weights.

##### Goal T1 & T5: Eliminate the `index_frame` (7.05 s/frame) and `_lzw` (0.47 s/frame) streaming bottlenecks

- **Option Gem-T1a: 3D RGB -> Palette Lookup Table (6-bit `64^3` or 7-bit `128^3` flat LUT) built once per clip.**
  - **How:** Once `_shared_palette` produces the 256-color palette, precompute the nearest palette index for a uniform 3D RGB grid (`64x64x64 = 256 KiB` or `128x128x128 = 2 MiB`) in one BLAS `pts @ palette.T` call (~100 ms once per clip). For each frame, apply the pre-tiled `8x8` integer Bayer offset in `int16`, bit-shift to grid coordinates `(r << 12) | (g << 6) | b`, and index `lut_1d[flat_key]`.
  - **Expected gain:** **920x speedup on `index_frame`** (**7,052 ms -> 7.66 ms/frame** on 1 CPU thread; cuts 2,232-frame indexing from **4.37 hours to 17.1 seconds**).
  - **Cost and risk:** Low (~25 lines in `encode.py`). Can sit behind the quality/speed setting (or default to `128^3` 7-bit LUT in `balanced` and exact BLAS in `exact`).
  - **Equivalence to current output:** `64^3` LUT matches exact palette index on 78.2% of dithered pixels with **1.87/255 RGB RMSE**; `128^3` (7-bit) LUT matches >90% of pixels with **<0.85/255 RGB RMSE** (visually indistinguishable).
  - **Evidence tag:** **[M]** measured on frame 0 of the 326 MB test GIF + **[C]** FFmpeg `paletteuse` 3D LUT architecture.

- **Option Gem-T1b: Exact BLAS `sgemm` distance decomposition for `exact` mode.**
  - **How:** Replace `((chunk[:, None, :] - palette[None, :, :]) ** 2).sum(axis=2)` in `encode.py:269` with `0.5 * (palette ** 2).sum(axis=1)[None, :] - chunk @ palette.T` (and pre-tile the Bayer matrix once per clip instead of calling `np.mgrid` on every frame).
  - **Expected gain:** **15x speedup on `index_frame`** (**7,052 ms -> 467 ms/frame** on CPU, or **<0.5 ms/frame** on GPU via `torch.cdist` / `matmul`).
  - **Cost and risk:** Trivial (5 lines in `encode.py`).
  - **Equivalence to current output:** **Bit-identical** palette indices.
  - **Evidence tag:** **[M]** measured above.

- **Option Gem-T1c: Replace pure-Python `_lzw` (`encode.py:90`) with C-compiled LZW (Pillow C `GifEncode` or C++ flat-DFA LZW in `backend`).**
  - **How:**
    1. *Zero-build fallback:* Encode the `uint8` indexed `Image.fromarray(index, mode="P")` to an in-memory `io.BytesIO` via Pillow's C `GIF` encoder and write the image data sub-blocks into `IndexedGifWriter` (or stream frames directly through Pillow's incremental C encoder).
    2. *Native `backend` path:* Implement a 40-line C++ LZW compressor in `backend` using a flat contiguous transition table `int16_t next_code[4096][256]` (2 MiB, fits in L2 cache, zero hash-table allocations, `memset` on clear code).
  - **Expected gain:** **25x speedup** with Pillow C (**474.5 ms -> 18.9 ms/frame**, **42 s** for 2,232 frames) or **~150x speedup** with C++ flat-DFA LZW (~3 ms/frame, **6.7 s** for 2,232 frames; also parallelizable across frames since each GIF frame's LZW stream is independent!).
  - **Cost and risk:** Low.
  - **Equivalence to current output:** Lossless LZW compression of the exact same `uint8` index buffer (decoded pixels are **100% bit-identical**).
  - **Evidence tag:** **[M]** measured Pillow C GIF encode at 18.93 ms/frame.

- **Option Gem-T1d: Single-pass streaming decode + Reservoir/Unscaled Palette Sampling (eliminates the first half-clip decode pass).**
  - **How:** Currently `_palette_samples` (`pipeline.py:147`) decodes from frame 0 to frame 2,093 (~94% of the clip!) and scales 16 frames just to build the 256-color median-cut palette, then `_resample_gif_stream` re-opens the GIF and decodes all 2,232 frames a second time. Two sub-options (behind the palette setting per D5):
    1. *Unscaled stride sample:* Build the median-cut palette from the unscaled sampled source frames (Lanczos3-dering preserves local color convex hulls by definition because the dering clamp restricts RGB to `[lo, hi]` of the source neighborhood!). Saves 16 scale calls.
    2. *First-K window + scene-cut check:* Build the palette from the first $K=64$ frames (~0.35 s decode) or a bounded read-ahead buffer so the file is only decoded **once**.
  - **Expected gain:** Saves **11–16 seconds** of duplicate GIF decoding + scaling before the progress bar even starts moving.
  - **Cost and risk:** Low; gated behind the palette setting (D5).
  - **Equivalence to current output:** Unscaled palette sampling is perceptually identical (since deringed Lanczos never creates colors outside the source neighborhood); first-$K$ window can miss late-appearing colors if a clip changes scene completely.
  - **Evidence tag:** **[M]** measured decode speed + mathematical invariant of `_clamp_rgb_to_neighborhood`.

- **Option Gem-T1e: Dirty-rectangle (`diff_mode`) delta scaling + encoding (behind setting per D6).**
  - **How:** In `iter_gif_frames`, expose the raw frame disposal and bounding box `image.tile` / `dispose_extent` (or compute the bounding box `[y0:y1, x0:x1]` where `curr_rgba != prev_rgba`). Expand `[y0:y1, x0:x1]` by the Lanczos3 support margin (`+3` source pixels on each side), scale + dering only that sub-rectangle, and splice it into the previous scaled canvas. Similarly, in `IndexedGifWriter.add_frame`, write only the changed sub-rectangle `(left, top, sub_w, sub_h)` with disposal=1 (`do not dispose`) and transparent unchanged pixels when beneficial.
  - **Expected gain:** **2x to 10x** on animations/cinemagraphs/wallpapers with static backgrounds, and smaller output GIF files.
  - **Cost and risk:** Medium (must pad the sub-rectangle by $\lceil \text{support} \rceil + 1 = 4$ source pixels so boundary taps and the $6\times 6$ clamp window see the exact surrounding canvas). Gated behind an explicit setting per D6.
  - **Equivalence to current output:** **Bit-identical** to full-frame scaling when padded by 4 source pixels on all sides!
  - **Evidence tag:** **[C]** FFmpeg `diff_mode=rectangle` + mathematical support radius of `lanczos_kernel(3.0)`.

##### Goal T3 & T4: GPU + Multi-Core CPU Execution (`workers` & Arbiter-aware GPU batching)

- **Option Gem-T3a: Fused GPU Pipeline (Scale + Dering Clamp + Palette Indexing on GPU, overlapped with CPU Decode & C-LZW).**
  - **How:** Since `index_frame` on CPU takes 467 ms (exact BLAS) or 7.7 ms (LUT), when running on the RTX 3090 Ti (automatic default per D11/D16), keep the scaled batch of $B$ frames on the GPU and run **Bayer dithering + exact palette nearest-neighbor (`torch.cdist` / `pal_norm - flat @ pal.T`) directly on the GPU** before transferring back to CPU!
    - Transferring `uint8` indexed frames (`B x 800 x 1440 x 1` byte = **1.15 MB/frame**) over PCIe instead of `float32` RGBA (`B x 800 x 1440 x 16` bytes = **18.4 MB/frame**) cuts Device-to-Host PCIe bandwidth by **16x** and makes exact 256-color Euclidean lookup cost **<0.3 ms/frame** on the 3090 Ti!
    - Dynamically size batch $B \in [4, 64]$ from `GPULeaseArbiter` free VRAM at batch start and release tensors between batches (D16).
  - **Expected gain:** Scale + exact dither/index in **~3.7 ms/frame** on RTX 3090 Ti (**~8.2 s** total for all 2,232 frames!), overlapped with CPU decode (12.4 s) and multi-threaded C/C++ LZW encode (~7–15 s) -> **entire 2,232-frame GIF finishes in ~20–25 seconds end-to-end**.
  - **Cost and risk:** Low-Medium (~120 lines in a GPU executor module, integrated with `gpu_lease_arbiter.py`).
  - **Equivalence to current output:** Float32 scale within `6.6e-5`, palette indexing **bit-identical** to exact Euclidean distance.
  - **Evidence tag:** **[M]** scale step 3.4 ms/frame + PCIe bandwidth calculation.

- **Option Gem-T4a: Producer-Consumer Pipeline with ThreadPool (for GIL-releasing C++/OpenBLAS/OpenCV stages) and `workers` setting.**
  - **How:** Because Option Gem-T2a (`cblas_sgemm` + `cv2.erode`/`dilate`/`remap`), Option Gem-T2b (C++ `backend`), and Pillow C GIF encode / C++ LZW **all release the Python GIL**, intra-file parallelism (`workers = N`) can use a **bounded `ThreadPoolExecutor(max_workers=workers)`** (with `OPENBLAS_NUM_THREADS=1` and `cv2.setNumThreads(1)` per worker to prevent thread oversubscription) instead of `ProcessPoolExecutor`!
    - Avoids IPC pickling of 32 GB of raw frame buffers across processes.
    - Sequential decoder thread pushes `(frame_idx, rgba_u8, duration)` into a bounded queue (`maxsize = 2 * workers`); `workers` threads run `scale + dering + index + lzw_compress` in parallel (returning compressed LZW `bytes` per frame); writer orders by `frame_idx` and writes sequentially to disk.
    - Checks `ResampleCancelled` before/after every frame so cancellation remains `< 0.05 s`.
  - **Expected gain:** Near-linear scaling with `workers` on CPU: at `workers=8` with Gem-T2a + Gem-T1a + Gem-T1c, **81 ms/frame / 8 ≈ 11 ms/frame -> ~25 seconds total for 2,232 frames on CPU alone** (and ~6 seconds with native C++ Gem-T2b).
  - **Cost and risk:** Low; avoids multiprocessing fork/spawn hazards with Qt/CUDA.
  - **Equivalence to current output:** Identical to single-worker output (frame order is strictly preserved).
  - **Evidence tag:** **[M]** verified GIL-releasing C calls (`cblas_sgemm`, `cv2`, Pillow C `GifEncode`).

#### Recommendation, with reasons and what would change your mind

1. **Fix the two hidden streaming bottlenecks (`index_frame` and `_lzw`) immediately alongside `lanczos3-dering`:**
   Our measurements prove that in `_resample_gif_stream`, `index_frame` (**7,052 ms/frame**) and pure-Python `_lzw` (**474.5 ms/frame**) take **25x longer than `lanczos3-dering` (294.2 ms/frame)** and run inside the `"scale"` progress loop. Adopting **Gem-T1a/b** (7-bit 3D LUT in `balanced`/`fast` mode, exact BLAS in `exact` mode) + **Gem-T1c** (C/C++ LZW) reduces indexing + LZW from **7,526 ms/frame to 26.6 ms/frame (or ~10 ms with C++ LZW)** — a **280x speedup** on that portion alone.
2. **For CPU `lanczos3-dering` (T2), ship Gem-T2a (precomputed `Wy`/`Wx` + 2D `sgemm` + `cv2.erode`/`dilate`/`remap` + opaque fast path) as the NumPy/OpenCV fallback, and Gem-T2b (fused row-strip C++/AVX2 kernel in `backend`) as the native CPU path:**
   Even on `workers=1` with no GPU and no C++ build, **Gem-T2a + Gem-T1a + Gem-T1c** finishes the entire 2,232-frame test GIF in **~181 seconds total** (with `scale = 109 s` and `encode = 59 s`, meeting Harbinger's D14 ~2-minute per-stage budget on a single CPU thread!). With the native C++ kernel (**Gem-T2b**) or `workers > 1` (**Gem-T4a**), CPU runtime drops to **15–35 seconds**.
3. **For GPU (T3), fuse palette indexing onto the GPU (**Gem-T3a**):**
   Running Bayer dither + exact palette lookup on the GPU right after `Wy @ premul @ Wx` avoids slow CPU indexing and cuts PCIe transfer volume by 16x (`1 byte/pixel` instead of `16 bytes/pixel`), finishing the entire 2,232-frame GIF in **~20–25 seconds**.
4. **What would change my mind:** If downstream callers require `resize_separable` to support custom non-local Python callables in `dering` that cannot be expressed as a neighborhood min/max window, or if a clip uses non-uniform per-frame dimensions (impossible in standard GIF89a after canvas compositing).

#### Questions for Harbinger

- **G-Q1 (Progress bar truthfulness):** Right now `_resample_gif_stream` (`pipeline.py:115-121`) runs `scale`, `index_frame` (dither + palette lookup), and `writer.add_frame` (LZW compression) inside every iteration of the `"scale"` progress loop, and only reports `"encode"` after the loop finishes. Should the streaming progress bar report `"Scaling & encoding frame N/2232"` (or split stage timing metrics in the completion summary into `decode`, `palette`, `scale`, `index/dither`, `lzw_write`) so the stage budgets in D8/D14 are visible and measurable?
- **G-Q2 (Palette indexing mode in `balanced` vs `exact`):** Is a 7-bit (`128x128x128`, 2 MiB) 3D LUT (which runs in 7.7 ms/frame with `<0.85/255` RGB RMSE) acceptable as the default in `balanced`/`fast` mode while keeping exact Euclidean BLAS/GPU lookup in `exact` mode?

### 5.9 Codex — 2026-10-30: Lanczos schedules and bounded execution

Read today's bus and the current resize/streaming implementation. No new benchmarks or GPU work run; numerical gains below are hypotheses, not measurements. Gemini's measurements remain attributed to Gemini. Respect D10 (workers default 1), D14 (per-stage budget), D16 (arbiter), and D22 (7-bit LUT permitted).

**Code anchors:** `classical/_resize.py:196` builds plans; `:213` gathers once per tap; `:236` copies a full transposed intermediate; `:277` allocates full-resolution clamp bounds; `:147` and `:160` copy/restore alpha. `encode.py:259` does palette lookup separately. These are opportunities to reduce memory traffic, not just arithmetic.

| Goal / option | How | Expected gain | Cost and risk | Equivalence to current output | Evidence |
|---|---|---|---|---|---|
| T2 / Cx-A: reusable execution plan | Build immutable indices, normalized weights, validity masks and active taps once per geometry/kernel; keep private reusable scratch per worker across streaming calls and palette sampling. | Removes O(frame count) plan construction and repeated allocation; modest alone. | Low–medium; bound cache size and never share writable scratch between workers. | Can preserve operation order and float32 results; verify borders and concurrent jobs. | [H], code anchors above. |
| T2 / Cx-B: rational-scale phase kernel | Specialize common 2x/3x ratios: interior pixels use a small repeating set of coefficient phases; retain the generic plan for boundaries and arbitrary dimensions. SIMD across contiguous output pixels. | Less coefficient/index traffic and gather overhead; factor unknown. | Medium; distinct border normalization and half-pixel phase must survive. | Same kernel, rounding differences if SIMD/FMA changes reduction order. | [H]. |
| T2/T5 / Cx-C: native fused row strips | In `backend`, compute horizontal filtered rows plus source RGB min/max rows into ring buffers; vertically filter, clamp, restore alpha, and emit output strips without full-frame transposes or full `lo`/`hi` images. Release GIL. | Scratch scales with strip width and support rather than output area; likely strongest CPU memory-traffic improvement. | High; more native code, portable scalar fallback plus SIMD dispatch needed. | Preserve premultiplied clamp and alpha threshold exactly; float32 tolerance must be measured. | [H]; [Halide async/ring-buffer tutorial](https://halide-lang.org/docs/tutorial/lesson_24_async.html) demonstrates scheduling, not our speedup. |
| T2 / Cx-D: library comparison path | Compare libvips float premultiplied Lanczos plus our clamp against Cx-C; use Pillow-SIMD as a throughput reference rather than assume it replaces deringing. | Potentially faster route to native throughput; no project speed guarantee. | Medium; dependency/build cost, coordinate/border and intermediate-clipping differences. Explicit experimental path. | Not established; no claim of identical kernels or output. | [C] [libvips execution model](https://www.libvips.org/API/8.16/How-it-works.html) explains region-based low-memory execution; [Pillow-SIMD](https://github.com/uploadcare/pillow-simd) supplies optimized operations, not our clamp semantics. |
| T3 / Cx-E: sparse GPU gather versus dense GEMM | Compare a six-tap fused GPU kernel with existing dense-matrix prototype. Cache device plans; retain scaled pixels through Bayer/index lookup; return indexed bytes. | Sparse arithmetic scales with taps rather than source dimension; dense GEMM may still win at this small size. No assumed winner. | High for custom kernels; batch sizing, upload, synchronization and arbiter handoff included in timing. | Float tolerance plus palette decision stability must be checked separately. | [H]; extends Gemini's GPU direction without claiming new measurements. |
| T1/T4/T5 / Cx-F: bounded staged pipeline | Sequential compositing decoder, native frame workers, ordered writer. Bound total in-flight bytes including out-of-order completed frames, not only input queue length. Share global CPU budget with batch jobs. | Overlap stages; ideal throughput limited by slowest stage, memory bandwidth and serial decode/write. | Medium; avoid unbounded executor submission and nested BLAS/OpenCV pools. Cancel queued work and check between strips. | Frame order, duration, loop and disposal preserved. | [H]; [libvips threading](https://www.libvips.org/API/8.16/using-threads.html) documents explicit concurrency control; no near-linear guarantee. |

**Recommendation:** optimize indexing and native LZW alongside Lanczos first. On Gemini's reported split (96.2% indexing/LZW), making only Lanczos 6x faster improves the loop by roughly 1.03x, not 6x (Amdahl estimate, not an end-to-end measurement). Start Lanczos work with Cx-A and compare dense CPU/morphology against Cx-C; prefer measured performance and bounded memory over a predetermined implementation. Keep GPU indexing on-device. Validate a small representative frame set before requesting an authorized full-file run.

**Acceptance evidence to collect:** opaque and transparent edges, tiny/odd dimensions, impulse/checkerboard, arbitrary resize ratios, border extrema and palette ties. Report float max/RMS error, decoded-GIF color error and temporal stability separately. Proposed tolerances need verification: <=1/255 straight RGB on visible pixels for balanced mode; report alpha independently and handle near-zero alpha explicitly. Include warm/cold setup, stage wall times, cancellation latency and peak RSS/VRAM. A one-frame timing multiplied by 2232 is a projection, not a completed-job result.

## 6. Replies and disagreements

### Codex — 2026-10-30: equivalence caveats for §5.8

- A channel-wise dering min/max box is not a color convex hull. Resampling creates new colors inside that box; sampling unscaled frames may therefore change the palette. This remains a useful D5 option, but perceptual equivalence needs a comparison.
- Delta scaling needs global output coordinates and Bayer phase, the original resize ratio, disposal-aware composited changes, and the exact dependency halo. Padding a locally resized crop by four pixels alone does not establish bit identity, especially at non-integer scales.
- Small float differences can flip nearest-palette assignments at ties; BLAS distance reformulation can change ties through cancellation. Deterministic tie-breaking and decoded-color error should accompany float error.
- Near-linear CPU scaling, sub-frame cancellation bounds and whole-job GPU times are hypotheses until measured with all stages and bounded queues. Threadpool limits should be set centrally: OpenCV thread count is process-wide, not a private per-worker control.


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
| 8 | "A couple of minutes" is the whole job, decode to written file, for 2232 frames at 2x with `lanczos3-dering`? Roughly 120 to 180 s, so about 50 to 80 ms per frame end to end. | Claude | Each stage (decode, palette, scale, index/dither, write) should take at most about a couple of minutes. See Q14: this reads as a per-stage budget, not a whole-job one. | Harbinger | 2026-10-30 |
| 9 | Should the settings be grouped as one quality/speed mode (for example `exact`, `balanced`, `fast`) with the individual switches under an advanced section, or only individual switches? | Claude | Include the advanced individual switches (alongside a simple mode). | Harbinger | 2026-10-30 |
| 10 | `workers` global default: `auto` (all cores minus one) or a fixed fraction? Should the GUI stay responsive by default (leave cores free)? | Claude | A setting or parameter, default 1. Above 1 (intra-file multi-core, for long jobs) must show a warning when batch multi-core (for many small jobs) is also on, because both together are likely to saturate the machine. | Harbinger | 2026-10-30 |
| 11 | When a GPU is present, should the GPU path be the automatic default, with a global setting to force CPU? And a cap on how much VRAM one job may take (default)? | Claude | Yes: GPU runs automatically when present. Default VRAM per job is all available VRAM, with a setting to change it. | Harbinger | 2026-10-30 |
| 12 | The native C++ kernel needs the `backend` extension built. If it is missing, fall back to NumPy with a visible warning, or refuse the job? | Claude | Fall back (to NumPy) and tell the user it did. | Harbinger | 2026-10-30 |
| 13 | Should the app show which path ran (GPU / native / NumPy, palette mode, delta mode) in the finish message so results are explainable? | Claude | Yes: show which path ran. | Harbinger | 2026-10-30 |
| 14 | Q8 says each stage may take a couple of minutes. Do you mean a **per-stage** budget (so the whole job may total several minutes), or should the **total** also stay near a couple of minutes? On this machine with the GPU the total looks reachable; on CPU with `workers=1` it likely is not. | Claude | About 2 minutes or so per stage (confirmed: a per-stage budget). | Harbinger | 2026-10-30 |
| 15 | With `workers` default 1, the CPU-only path stays single-core unless the user raises it. Is that the intended default even when no GPU is present, or should `workers` default to a higher value automatically when there is no GPU and the job is long? | Claude | No silent auto-default. When no GPU is detected and the job will be long, show a window with a warning that jobs will take a long time, and let the user either continue anyway or enter a number of CPU workers. If the user accepts a number, it becomes the default value of the `workers` setting. | Harbinger | 2026-10-30 |
| 16 | "All available VRAM per job" can starve other GPU work (ComfyUI, training). Should the GPU lease arbiter (`middleware/src/core/gpu_lease_arbiter.py`) cap it so a job takes what is free at start and waits or shrinks its batch if another job holds the GPU? | Claude | Yes. The job takes what is free at start, releases it as work completes, and adapts when other jobs request or hold the GPU (arbiter-managed). | Harbinger | 2026-10-30 |
| 17 | The "no GPU detected" window: when exactly does it appear? Proposal: only when no usable GPU is found **and** the estimated runtime exceeds a threshold (for example 2 minutes, estimated from a timed sample of the first frames). Short jobs would not ask. Is that right, and what threshold? | Claude | Yes. Appears only when no usable GPU is found and the estimated runtime exceeds the threshold. Default threshold 2 minutes, user-changeable in settings. | Harbinger | 2026-10-30 |
| 18 | Should the window offer "do not ask again" (and where is that reset, in Settings)? Also what is the default choice if the user closes the window: cancel the job, or continue with the current `workers`? | Claude | Yes: a "do not ask again" option, backed by an on/off flag in Settings. Closing/exiting the window cancels the job. Enter accepts the currently chosen number of workers. Shift+Tab proceeds without more workers (see Q20 on that key). | Harbinger | 2026-10-30 |
| 19 | **UI freeze conflict.** `AGENTS.md` (W0-20) freezes `gui/src` (the PySide6 shell you launch with `just python`) to reviewed bugfixes: new Qt panels and dialogs are rejected unless Harbinger approves an `[[exception]]` in `migration/features.toml`. This window and the new settings need UI. Options: (a) build them in the Tauri frontend only (the Qt Sampler would not get them); (b) approve an exception so the Qt Sampler gets the window and settings too; (c) build the logic UI-agnostic in `middleware` (a pre-flight "estimate" service call plus settings) and wire both shells later. Which? | Claude | Take Claude's recommendation: (c) keep the logic UI-agnostic in `middleware` (pre-flight estimate call plus settings), with (b) a recorded exception so the Qt Sampler also gets the window and settings; Tauri wiring follows. Reason: Harbinger is still building the Tauri parity tests, which resume after this optimization round. | Harbinger | 2026-10-30 |
| 20 | Keys in the window: Enter = accept the chosen worker count, Esc/close = cancel, and you said Shift+Tab = continue without more workers. Shift+Tab is normally "previous field" in Qt and web, so it may fight focus navigation. Keep Shift+Tab as written, or use another shortcut (for example Shift+Enter) and show it on the button label? | Claude | Use Shift+Enter instead of Shift+Tab to continue without more workers; show the shortcut on the button label. | Harbinger | 2026-10-30 |
| 21 | (G-Q1, Gemini) Should the streaming progress bar report scaling and encoding together ("Scaling & encoding frame N/total") and/or put per-stage timings (decode, palette, scale, index/dither, LZW write) in the finish summary? | Gemini | Both. | Harbinger | 2026-10-30 |
| 22 | (G-Q2, Gemini) Is a 7-bit (128^3) color lookup table acceptable as the default palette indexing in `balanced`/`fast` modes, with exact lookup kept for `exact`? | Gemini | Yes. | Harbinger | 2026-10-30 |

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
| D8 | Time budget is stated per stage (about 2 minutes each); total target pending Q14. | Q8 | | Harbinger | 2026-10-30 |
| D9 | Settings: a simple mode plus the advanced individual switches. | Q9 | | Harbinger | 2026-10-30 |
| D10 | `workers` default 1; above 1 warns when batch multi-core is also enabled. Intra-file workers are for long jobs, batch multi-core for many small jobs. | Q10 | Both together can saturate the machine. | Harbinger | 2026-10-30 |
| D11 | GPU path is automatic when present; default VRAM per job is all available, adjustable by a setting. | Q11 | | Harbinger | 2026-10-30 |
| D12 | Missing native extension: fall back and tell the user. | Q12 | | Harbinger | 2026-10-30 |
| D13 | The finish message states which path ran (device, kernel, palette mode, delta mode). | Q13 | | Harbinger | 2026-10-30 |
| D14 | The time budget is about 2 minutes per stage. | Q14 | | Harbinger | 2026-10-30 |
| D15 | No GPU detected, long job: show a warning window ("jobs will take a long time") offering continue anyway or a CPU worker count; an accepted count becomes the default of `workers`. | Q15 | Avoid silent slow runs and silent saturation. | Harbinger | 2026-10-30 |
| D16 | The GPU job takes what is free at start, releases as it completes, and adapts to other jobs through the arbiter. | Q16 | Do not starve ComfyUI or training. | Harbinger | 2026-10-30 |
| D17 | The no-GPU window appears only when no usable GPU is found and the estimated runtime exceeds a threshold; default 2 minutes, adjustable in settings. | Q17 | Short jobs should not prompt. | Harbinger | 2026-10-30 |
| D18 | The window has "do not ask again" with an on/off flag in Settings; closing cancels the job; Enter accepts the chosen worker count; a second key proceeds with no extra workers (exact key pending Q20). | Q18 | | Harbinger | 2026-10-30 |
| D19 | UI approach (c)+(b): UI-agnostic pre-flight estimate and settings in `middleware`, plus a recorded `[[exception]]` in `migration/features.toml` so the Qt Sampler gets the window and settings; Tauri wiring after the Tauri parity tests resume. | Q19 | Harbinger is still doing the Tauri parity tests; they resume after this optimization round. | Harbinger | 2026-10-30 |
| D20 | "Continue without more workers" is Shift+Enter (shown on the button label), not Shift+Tab. Enter accepts the chosen worker count; closing cancels. | Q20 | Shift+Tab is focus navigation. | Harbinger | 2026-10-30 |
| D21 | The streaming progress text reports scaling and encoding together, and the finish summary lists per-stage timings (decode, palette, scale, index/dither, LZW write). | Q21 | Makes the per-stage budget visible. | Harbinger | 2026-10-30 |
| D22 | `balanced`/`fast` palette indexing may use a 7-bit (128^3) lookup table; `exact` keeps exact nearest-color lookup. | Q22 | Measured by Gemini at 7.7 ms/frame, under 0.85/255 RGB RMSE; 920x faster than today's exact path. | Harbinger | 2026-10-30 |

## 9. Final implementation roadmap

_(Written after the decisions: ordered tasks, owners, issues, acceptance numbers.)_
