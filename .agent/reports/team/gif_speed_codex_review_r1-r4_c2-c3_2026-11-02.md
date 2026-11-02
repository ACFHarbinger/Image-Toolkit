# GIF speed review — 2026-11-02

**Do not merge this stack as submitted.** R2 introduces unsafe admission behavior for existing GPU users; R3 has retry and production-routing gaps; C3 blocks the GUI during estimation.

Review was read-only. No edits, checkouts, commits, merges, pushes, or rebases were performed.

Read `AGENTS.md`, Grok’s final bus section, the spec including D1–D29, all six issue bodies, and branch diffs against their stated parents. `gh issue view` failed to connect; the connected GitHub tool retrieved the issue bodies.

All findings below are **from code inspection**, not passing tests.

| Branch | Reviewed tip | Verdict |
|---|---|---|
| R2 | `48b91ffce` | **DO NOT MERGE** |
| R1 | `93ea0ac07` | **MERGE AFTER FIXES** |
| R3 | `0202ea9fb` | **MERGE AFTER FIXES** |
| R4 | `b407c5f30` | **MERGE AFTER FIXES** |
| C2 | `f94f2dbf3` | **MERGE AFTER FIXES** |
| C3 | `526541d63` | **DO NOT MERGE** |

Stacked branches also inherit their ancestors’ blockers. Paths below are relative to the corresponding `~/Downloads/Data/Tests/gif-speed-<id>/` worktree.

## R2 — shared GPU lease, #1171

**Acceptance:** The new tests cover a held legacy lease refusing GIF admission and GIF ownership appearing in the shared snapshot. They do not establish compatibility with existing consumers after device-table attachment.

1. **HIGH — Existing consumers can lease one card and execute on another.**  
   `middleware/src/core/gpu_lease_arbiter.py:375` permanently enables per-device admission; `:769` selects the freest available card. Existing `try_admit` callers receive only success/refusal, not a device.

   For example, `gui/src/helpers/models/training_worker.py:31` acquires without specifying a device, then `:49` uses `self.device_name`. A GIF holding `cuda:0` can therefore coexist with training granted `cuda:1` while training actually executes on `cuda:0`. Neural users such as `middleware/src/services/media/gif_upscale/neural/hat.py:425` similarly choose generic `"cuda"` independently. Comfy submissions also do not route their external execution according to the selected lease.

   **Confidence: high, read from code.** Preserve global exclusion for consumers without device routing, or update admission and execution together.

2. **HIGH — First attachment races with a legacy acquisition.**  
   `middleware/src/core/gpu_lease_arbiter.py:474` checks `_slots` before acquiring `_transition`; `:496` subsequently enters legacy acquisition without rechecking.

   A caller can observe no table, pause, then resume after `ensure_device_table` installs one at `:375`. It acquires legacy ownership without a device slot. Subsequent release follows the device-table path and finds no matching slot, leaving legacy lock/ownership state inconsistent and allowing conflicting admission.

   **Confidence: high, read from the lock ordering.** Table selection and acquisition must be atomic with attachment.

**Tests:** Useful admission behavior tests, but fake sessions and sequential attachment miss both failures. Add existing-consumer compatibility and deterministic attachment-race coverage.

**Other processes:** The lease remains in-process only. External ComfyUI occupancy is represented by a free-VRAM observation, not coordinated exclusion.

## R1 — release VRAM, #1170

**Acceptance:** Success-path cleanup, fake-device coverage, and a CUDA-skipped measurement test exist. Grok reported reserved memory falling from 24 MiB to zero; I did not reproduce that measurement.

1. **HIGH — Failure cleanup can still leave reserved VRAM behind.**  
   `middleware/src/services/media/gif_upscale/gpu_batch.py:609` releases admission after constructor failure without cache cleanup. Earlier constructor allocations can remain reserved after the exception unwinds.

   Also, `close()` at `:491` performs its only cleanup while callers handling a GPU exception may still retain that exception’s traceback and its batch tensors. Those tensors become allocator cache after unwinding; later `close()` calls return immediately because `_closed` is already set.

   **Confidence: high for the cleanup gap; actual retained bytes unmeasured.** Cover partial initialization and cleanup after exception-held tensors are released.

2. **MEDIUM — The real-device regression can pass without freeing the measured allocation.**  
   `middleware/test/services/gif_upscale/test_gpu_cache_r1.py:127` allows 64 MiB above baseline. Grok’s entire measured allocation was about 24 MiB, so retaining all of it satisfies the assertion; the strict reduction check is conditional on exceeding that slack.

   **Confidence: high, read from assertions.** Require a meaningful reduction relative to the allocation actually observed.

**Concurrency concern:** `gpu_batch.py:500` clears process-wide cuBLAS workspaces while other device holders may still execute. Holding this session’s lease does not establish process-wide quiescence. This needs documented safety evidence or coordination; I have not confirmed a resulting CUDA failure.

**Output/cancellation:** No numerical kernel change was introduced. Successful close drops the listed session tensors before releasing admission.

## R3 — OOM batch shrinking, #1172

**Acceptance:** The tests cover one halving, one transient singleton failure, repeated singleton failures, ordered fake output, and finish-message notes. Important production cases remain broken.

1. **HIGH — Queued tails are not resized after subsequent shrinking.**  
   `middleware/src/services/media/gif_upscale/gpu_schedule.py:564` returns a local retry unchanged. `:606` splits only the currently failing job.

   Example: batch four fails; its two-frame head fails; the session shrinks to one. Frames zero and one then succeed individually, but the earlier two-frame tail is attempted intact. Its OOMs are counted as failures “at batch size 1,” and the card is retired even though every singleton fits.

   **Confidence: high, read from queue operations.** Split every dequeued retry to the current batch limit, including retries received from other cards.

2. **HIGH — A job with only one acquired GPU bypasses this recovery.**  
   `middleware/src/services/media/gif_upscale/pipeline.py:258` enters the scheduler only when more than one session exists. The single-session stream path at `:674` retires directly to CPU on an exception. The in-memory single-session loop at `:134` likewise has no shrinking recovery.

   This affects one-card machines, pinned jobs, and two-card machines where one card is unavailable.

   **Confidence: high, read from production routing.** Route single-session work through the recovery logic too.

**Tests:** These exercise real scheduler control flow, not merely mock call counts, but only cover a narrow fake workload. Add repeated shrinking with queued tails and production entry-point coverage.

**Output/cancellation:** Shrink notes reach the finish message. Explicit `ResampleCancelled` propagation and per-frame writer checkpoints remain present. Actual GIF bytes and GPU numerical equivalence were not verified.

## R4 — remove overlap module, #1173

**Acceptance:** Option (b) removes the module and its dedicated tests. The fused production call remains preferred. Grok’s bus explains the delivered thread-level concurrency and reports its measurement.

1. **MEDIUM — Current documentation still claims the removed implementation exists.**  
   `.agent/reports/team/gif_resample_speed_ideas_2026-10-30.md:333` says `run_device_pipeline` implements pinned-copy-stream overlap with multiple batches in flight. That implementation is deleted, and the branch changes no documentation.

   **Confidence: high, read from diff and reference search.** Update the current implementation description to say decode thread, one worker per device, and writer thread. Historical bus entries can remain historical, with a clear correction.

**References/tests:** The remaining Python reference to `gpu_overlap` is an intentional negative import assertion in `middleware/test/services/gif_upscale/test_gpu_schedule_b3.py:234`; I found no remaining production import. Historical bus references remain too.

Removing tests for deleted behavior is appropriate. Scheduler order, cancellation, and fused-call coverage remain; the replacement test checks sequential scale/index behavior for sessions lacking the fused method. No numerical kernel change was introduced by this deletion.

## C2 — estimate service, #1160

**Acceptance:** Provides measured sample stages, projections, device/path text, settings integration, and the combined-workers warning. The service needs stronger cancellation and device semantics.

1. **MEDIUM — Cancellation stops being frame-granular after decoding.**  
   `middleware/src/services/media/gif_upscale/estimate.py:238` scales the entire sample without progress/cancellation checkpoints. Indexing at `:258` reports only after all remaining frames; writing at `:289` has none.

   Cancellation requested during scaling can therefore wait through all sampled frames and indexing. The existing cancellation test exits during decoding and misses this.

   **Confidence: high, read from loops.** Add checkpoints between frames in each stage.

2. **MEDIUM — “Usable GPU” and projected device ignore actual admission constraints.**  
   `estimate.py:99` checks CUDA availability/count only; `:297` uses that result to predict execution. It ignores device allow-lists, shared holders, available capacity, and whether a pinned device exists. It can report “job would use cuda:1” when only `cuda:0` exists.

   **Confidence: high, read from probe and routing.** Use a request-aware eligibility check and describe admission as provisional.

3. **MEDIUM — The claimed CPU-only sampling is not enforced for registry algorithms.**  
   `estimate.py:147` accepts the selected registry algorithm, and `:241` calls it directly. Neural algorithms can acquire a GPU and run inference, despite `timed_device="cpu"` and `_job_device` labelling non-Lanczos algorithms CPU.

   **Confidence: high, read from dispatch and neural implementations.** Explicitly restrict supported estimates or implement truthful algorithm-specific sampling.

4. **LOW — Scratch handling violates the repository location rule and risks collisions.**  
   `estimate.py:275` defaults to the system temporary directory. With a supplied directory, `:283` always overwrites and deletes `gif-estimate-lzw.gif`, so concurrent estimates sharing that directory collide.

   **Confidence: high, read from file handling.** Use a unique directory under `~/Downloads/Data/Tests/`.

**Tests:** Tiny real GIFs exercise decode, scaling, indexing, writing, and cleanup. However, projection tests largely verify the implemented arithmetic; they do not validate predictive accuracy. Device tests inject the answer.

## C3 — Sampler no-GPU window, #1161

**Acceptance:** Enter/Shift+Enter, persistence, close-to-cancel, threshold, and flag behavior are implemented. The Qt freeze exception is no longer required under the current repository rules.

1. **HIGH — Preflight blocks the GUI thread.**  
   `gui/src/tabs/core/sampler_subtab/_resample_worker.py:54` synchronously calls `confirm_slow_gif`; `no_gpu_window.py:203` scans, decodes, scales, quantizes, indexes, and writes before creating the worker or showing the dialog.

   Large frames or expensive algorithms can freeze the UI, with no usable cancellation control during estimation.

   **Confidence: high, read from call chain.** Run estimation off the GUI thread and return through signals.

2. **HIGH — CUDA presence suppresses the warning even when this job runs on CPU.**  
   `no_gpu_window.py:198` returns before inspecting algorithm or job eligibility. The Sampler defaults to `lanczos`, while production GPU dispatch requires `lanczos3-dering` with the temporal encoder.

   Thus the default long Sampler job silently remains CPU-bound on a CUDA machine and never offers the worker-count window. Held or disallowed devices produce the same eligibility mismatch.

   **Confidence: high, read from routing.** This confirms Grok’s algorithm concern. It is separate from R2’s process-wide attachment bug.

3. **MEDIUM — Estimated dimensions differ from the actual request.**  
   `no_gpu_window.py:155` copies raw target dimensions. `gui/src/helpers/core/sampler_worker.py:200` fits dimensions to aspect ratio and supports width-only/height-only requests.

   A width-only request can fail estimation because height becomes zero, preventing a job the worker could run. Aspect-preserving jobs can also be estimated at the wrong pixel count.

   **Confidence: high, read from both dimension calculations.** Share the request-building logic.

**Tests:** Actual Qt key events test dialog behavior. Integration tests inject both GPU eligibility and estimates, so they miss GUI blocking, default-algorithm routing, and dimension mismatches. Sampling only the first GIF also means a short first GIF can hide expensive later jobs; that limitation should be explicit.

## Merge order and commands

**I would run no merge commands against these tips now.** After fixes, propagation through the stacked branches, and re-review, the dependency order is R2 → R1 → R3 → R4, with C2 → C3 independently.

From the existing main checkout, once those conditions are satisfied:

```bash
git merge --no-ff feat/gif-speed-r2
git merge --no-ff feat/gif-speed-r1
git merge --no-ff feat/gif-speed-r3
git merge --no-ff feat/gif-speed-r4
git merge --no-ff feat/gif-speed-c2
git merge --no-ff feat/gif-speed-c3
```

**These commands were not run.**

## Verification limits

Attempted only the authorized single-file CPU invocation of `test_gpu_schedule_r3.py`, with CUDA hidden and bytecode/cache writes disabled. Pytest failed **before collection** because the read-only sandbox had no writable temporary directory. **No tests ran.** Grok’s reported passes and GPU measurements were not independently reproduced.

Not checked: real CUDA execution, concurrent cuBLAS cleanup safety, two-card OOM injection, measured VRAM recovery, external-process contention, real GUI click-through, full-output byte equivalence, decoded-GIF color/temporal error, sustained memory bounds, or performance targets. No benchmarks, full suites, whole-file GIF processing, or GPU work were performed.