# Performance Roadmap — Compute, Memory, and I/O

*Last updated: 2026-05-31. All Tier 1–5 RAM reduction items are fully implemented (✅). These are the next-generation opportunities.*

---

## How to Use This Document

Each section describes a performance bottleneck, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping.

---

## 3.1 Rust Streaming Image Merger

**Pain point:** `base/src/core/image_merger.rs` loads all input images into a `Vec<DynamicImage>` before compositing. Merging 100 × 4K images temporarily consumes 2–4 GB of RAM.

### Options

**A — Two-pass streaming (sequential)**
Pass 1: read image headers only (parse width/height without decoding pixels — supported by the `image` crate via `image::image_dimensions()`). Compute final canvas dimensions from all headers. Allocate output buffer. Pass 2: decode each image one at a time, blit to canvas, drop immediately.
- Peak RAM: 1 image at a time (~30 MB for 4K RGBA) + output buffer (~200 MB for a 10K panorama).
- Pros: Near-minimal RAM usage during processing. No new dependencies.
- Cons: Two filesystem passes. Slower on spinning disks; acceptable on NVMe.

**B — Rayon-parallel with bounded semaphore**
Keep parallel load but limit concurrent live images to `N_cores` using a `tokio::sync::Semaphore` or `std::sync::Mutex<usize>`. Each thread acquires a permit before loading, releases after blitting.
- Peak RAM: `N_cores × image_size` (e.g., 8 cores × 30 MB = 240 MB).
- Pros: Balances throughput vs memory. Better I/O pipeline utilisation than sequential.
- Cons: Non-trivial semaphore integration with Rayon's work-stealing scheduler.

**C — Memory-mapped output buffer (memmap2)**
Use `memmap2` crate to map the output file directly into virtual memory. Each thread writes its strip directly to the mapped region; the OS flushes to disk lazily.
- Pros: Zero extra RAM for the output buffer. Particularly useful for panoramas >10K px.
- Cons: `memmap2` dependency. Output file must be pre-allocated to its final size. Random-write performance depends on OS page eviction policy.

**D — Streaming via pipes to ffmpeg**
For video-format outputs, pipe frame bytes to `ffmpeg` via stdin rather than accumulating in RAM. Handles arbitrary output sizes.
- Pros: Combines with §4.2 (scrolling video export).
- Cons: Only applicable when output format is video. Not useful for PNG/JPEG panoramas.

**E — Tile-based compositing**
Divide the canvas into N×M tiles. Process each tile independently (loading only the frame strips that intersect it). Write each tile directly to disk.
- Pros: Constant peak RAM regardless of canvas size.
- Cons: Frame strips may intersect multiple tiles, causing redundant decodes. Complex tiling logic.

**Recommendation:** A for correctness and simplicity. C as an optional flag for panoramas >10K px output. B for intermediate cases where parallelism is needed.

---

## 3.2 ASP Render Stage GPU Acceleration

**Pain point:** Stage 10 (temporal median render) averages 20.78s, single-threaded NumPy. The 10-frame, 4K canvas case (test19: 33.8s) is the dominant bottleneck.

### Options

**A — PyTorch stack + median on GPU (CUDA)**
Load frame strips as a CUDA tensor stack: `torch.stack([torch.from_numpy(f).cuda() for f in strips])`. Call `torch.median(stack, dim=0).values`. For a 4K × 4K canvas with 10 frames, expected reduction: 30s → 1–2s.
- Fallback: Detect `torch.cuda.is_available()`; fall back to NumPy if unavailable.
- Pros: Massive speedup on RTX 3090 Ti (already in the system). PyTorch already a dependency.
- Cons: GPU VRAM required: `N_frames × H × W × 3 bytes`. For 14 frames × 4K × 4K: ~672 MB VRAM — well within 24 GB.

**B — Numba JIT for NumPy path**
Decorate the median computation with `@numba.jit(nopython=True, parallel=True)`. No CUDA required; ~3–5× speedup on CPU using LLVM parallelism.
- Pros: No GPU required. Works in CPU-only environments.
- Cons: Adds Numba dependency (~500 MB installed). First-call compilation overhead (~2–5s on cold start).

**C — C extension via Cython**
Write the inner median loop in Cython with typed memoryviews.
- Pros: No large new dependency. Compile-time optimisation.
- Cons: Higher developer effort than B for similar result. Build step required.

**D — multiprocessing with shared memory**
Distribute frame strips across CPU cores using `multiprocessing.shared_memory`. Each core computes the median for a horizontal band.
- Pros: No new dependencies. Works on any hardware.
- Cons: 3–5× speedup at best (GIL is released for NumPy but memory bandwidth is the bottleneck). Shared memory setup overhead.

**E — Welford's online algorithm for streaming median**
Use an online median estimator (e.g., two heaps) that processes one frame at a time rather than stacking all frames. Reduces peak VRAM/RAM at the cost of approximation.
- Pros: Constant memory regardless of frame count.
- Cons: Approximate median; not bit-exact. Quality impact depends on frame distribution.

**Recommendation:** A for machines with the RTX 3090 Ti (already the target system). B as the CPU fallback for environments without CUDA. Skip C/D.

---

## 3.3 BiRefNet Inference Batching

**Pain point:** BiRefNet runs once per frame in sequence. For a 14-frame dataset, 14 serial GPU kernel launches underutilise the GPU between calls.

### Options

**A — Batch all frames in one forward pass**
Collate all frames into a single tensor batch: `torch.stack(frames, dim=0)`. One `model(batch)` call returns all masks.
- VRAM cost: `N_frames × H × W × 3 bytes`. For 14 frames × 1080p: ~87 MB — feasible on 3090 Ti.
- Pros: Maximises GPU utilisation. Eliminates kernel launch overhead.
- Cons: Memory spike at inference time. Must auto-detect VRAM before batching.

**B — Fixed-size mini-batches (e.g., 4 frames)**
Process 4 frames at a time as a compromise between latency and memory.
- Pros: Works on lower-VRAM GPUs (8 GB). Predictable memory usage.
- Cons: Less GPU utilisation than A for small datasets.

**C — Dynamic batching based on available VRAM**
At runtime, query `torch.cuda.mem_get_info()` and compute the maximum safe batch size: `batch = floor(free_vram / (H × W × 3 × dtype_size))`.
- Pros: Automatically adapts to available hardware. Uses A when VRAM is available; falls back to B.
- Cons: VRAM query adds a small overhead. OOM still possible if VRAM estimate is inaccurate.

**D — TorchScript/ONNX export for BiRefNet**
Export BiRefNet to TorchScript or ONNX and run via `onnxruntime`. ONNX Runtime applies graph-level optimisations and supports batching natively.
- Pros: Can be faster than raw PyTorch for inference-only workloads.
- Cons: Requires export step. Increases model management complexity.

**Recommendation:** C is the most robust production approach. A when VRAM allows; B as fallback. D is a [Research] item for deployment scenarios where PyTorch is unavailable.

---

## 3.4 Database Query Optimisation

**Pain point:** Several common database operations are suboptimal for large collections (>100k images).

### Options

**A — psycopg3 async connection pool**
Replace single-connection `psycopg2` with `psycopg3`'s async connection pool (`psycopg_pool.AsyncConnectionPool`). Reduces connection overhead for frequent small queries.
- Pros: Non-blocking queries; better utilisation of the Django/Celery layer. `psycopg3` is the current maintained library.
- Cons: Requires migrating from `psycopg2` API. Async patterns must propagate through callers.

**B — Prepared statements for hot paths**
Use `cursor.execute(prepared_stmt, params)` for queries called in tight loops (e.g., tag lookup per image). Avoids repeated query parsing overhead.
- Pros: 20–40% query overhead reduction for simple queries. Zero library change.
- Cons: Prepared statement cache invalidated by schema changes.

**C — Partial index on `images.path`**
`CREATE INDEX idx_images_path_prefix ON images(path varchar_pattern_ops)` speeds up `LIKE 'prefix%'` queries significantly for path-based filtering.
- Pros: One-time schema migration. Immediate query speedup.
- Cons: Additional index storage (~50 MB for 100k images). Index must be rebuilt on major path restructuring.

**D — HNSW index tuning for pgvector**
Current pgvector HNSW index likely uses defaults (`m=16`, `ef_construction=64`). For collections >100k images:
- Increase `m=32` for better recall at the cost of larger index size.
- Increase `ef_construction=128–200` for better index quality at build time.
- Tune `hnsw.ef_search=80–100` at query time for the speed-recall tradeoff.
- Expected improvement: 5–10× search latency for large collections.
- Reference: [pgvector HNSW tuning guide](https://deepwiki.com/pgvector/pgvector/5.1.4-hnsw-configuration-parameters); [Nerd Level Tech 2026 tuning tutorial](https://nerdleveltech.com/pgvector-hnsw-postgres-18-production-tuning-tutorial)

**E — Materialized view for tag aggregations**
Pre-compute common aggregations (image count per tag, most-used tags) as a PostgreSQL materialized view. Refresh on bulk ingest. Replaces slow `GROUP BY` queries in the search tab.
- Pros: Instant aggregation queries.
- Cons: Requires `REFRESH MATERIALIZED VIEW` after inserts. Adds schema complexity.

**F — Partition images table by ingest date or source**
Partition the `images` table by year or source crawler. Queries filtered by date range or source hit only the relevant partition.
- Pros: Large speedup for time-filtered queries.
- Cons: Partitioning is a significant schema migration. Adds complexity to cross-partition queries.

**Recommendation:** D is the highest-impact single change for large collections. B is a zero-risk, zero-migration quick win. A when the database tab is under latency pressure. C for path-heavy workloads.

---

## 3.5 WebDriver Lifecycle Management

**Pain point:** Selenium WebDriver instances are not guaranteed to be closed on Python exceptions, leaving orphaned browser processes consuming hundreds of MB each.

### Options

**A — Context manager wrapper in Python crawlers [Quick Win]**
Wrap each crawler session in:
```python
class CrawlerSession:
    def __enter__(self): return self
    def __exit__(self, *_): self.driver.quit()
```
`__exit__` always calls `driver.quit()`, even on exception.
- Note: Modern Selenium 4.x supports `with webdriver.Chrome() as driver:` natively.
- Reference: [Selenium context manager issue #3266](https://github.com/SeleniumHQ/selenium/issues/3266)
- Pros: Clean, Pythonic. Handles exceptions automatically.
- Cons: Must audit all existing crawler call sites.

**B — Rust RAII guard (scopeguard)**
In the PyO3 bindings, use `scopeguard::defer!` to call `quit()` on unwind. Handles panics as well as normal exits.
- Pros: Handles Rust-side panics that Python's `try/finally` doesn't see.
- Cons: Only applies to Rust-initiated crawls. PyO3 exception propagation across the boundary already converts panics to Python exceptions.

**C — Crawler health monitor thread**
Background thread that checks the WebDriver process list every 30s and kills orphans running >timeout.
- Pros: Catches failures in `driver.quit()` itself (rare but possible).
- Cons: Process enumeration is OS-specific. Adds a background thread overhead.

**D — Playwright as a WebDriver replacement**
Replace Selenium with Playwright, which has a built-in context manager and more reliable lifecycle management. Playwright's `async_playwright()` is inherently RAII.
- Pros: Better async support. More reliable than Selenium for modern SPAs. Active development.
- Cons: Large migration; Playwright and Selenium have different APIs. Requires updating all 4 crawler implementations.

**Recommendation:** A immediately. B if Rust crawlers are the primary path. D is a [Research] item worth evaluating for new crawler development.

---

## 3.6 DynamicImage Move Semantics in Rust

**Pain point:** Several Rust functions clone `DynamicImage` unnecessarily (e.g., `apply_ar_transform`, `fast_resize` no-op path). A 4K RGBA clone is ~32 MB per call.

### Options

**A — Change signatures to take ownership [Quick Win]**
`fn apply_ar_transform(img: DynamicImage, ...) -> Result<DynamicImage>`. Return `img` directly in the no-transform branch.
- Pros: Zero-cost when no transformation is needed. Clean Rust ownership model.
- Cons: Call sites must be updated to pass ownership. Can't easily share the image after calling.

**B — Cow<DynamicImage> (clone-on-write)**
Return `Cow::Borrowed(&img)` for no-op paths, `Cow::Owned(transformed)` for transform paths.
- Pros: Caller retains the original reference for no-op paths. Zero-copy in the common case.
- Cons: `image::DynamicImage` doesn't implement `Clone` cheaply — `Cow::Borrowed` avoids the clone, but the API is more complex.

**C — Arc<DynamicImage> for shared access**
Wrap images in `Arc<DynamicImage>` at intake. Cloning the `Arc` is cheap; actual pixel data is shared until a mutation is needed (where it would be cloned).
- Pros: Multiple pipeline stages can hold references to the same image without copying.
- Cons: `Arc` overhead for single-owner cases. Image crate's mutable operations require `Arc::make_mut()` (triggers clone on contention).

**Recommendation:** A. Call sites can afford the move. B adds complexity; C is overkill for this use case.

---

## 3.7 Python ML Model Memory Lifecycle

**Pain point:** Several ML models (BiRefNet, EfficientLoFTR, LightGlue) remain loaded in GPU VRAM after their pipeline stage completes. For pipelines that don't use all models, this wastes VRAM and slows subsequent GPU operations.

### Options

**A — Explicit unload after stage [Quick Win]**
Call `model.cpu()` + `del model` + `torch.cuda.empty_cache()` immediately after the model's pipeline stage. Already done for Siamese/GAN/SD3 wrappers — extend to BiRefNet and LoFTR.
- Pros: Frees VRAM immediately. Already-proven pattern in this codebase.
- Cons: Model must be re-loaded if the stage is retried (e.g., on RLHF re-run).

**B — LRU model cache with VRAM budget**
Keep the N most recently used models in a VRAM-bounded LRU. New model load triggers eviction of the least-recently-used.
- Pros: Avoids repeated load/unload for sequential processing runs.
- Cons: Requires tracking VRAM usage per model. More complex than A.

**C — Lazy load with weak references**
Load models only when first needed; hold via `weakref.ref`. Python GC reclaims when there are no strong references.
- Pros: Automatic lifecycle without explicit unload calls.
- Cons: GC timing is non-deterministic. `torch.cuda.empty_cache()` must still be called manually after GC.

**Recommendation:** A first (consistent with existing unload pattern). B for production mode where the same pipeline is run repeatedly.

---

## Anchor Index

| Section | Anchor |
|---------|--------|
| 3.1 Streaming Image Merger | [#31-rust-streaming-image-merger](#31-rust-streaming-image-merger) |
| 3.2 GPU Render Acceleration | [#32-asp-render-stage-gpu-acceleration](#32-asp-render-stage-gpu-acceleration) |
| 3.3 BiRefNet Batching | [#33-birefnet-inference-batching](#33-birefnet-inference-batching) |
| 3.4 Database Optimisation | [#34-database-query-optimisation](#34-database-query-optimisation) |
| 3.5 WebDriver Lifecycle | [#35-webdriver-lifecycle-management](#35-webdriver-lifecycle-management) |
| 3.6 Rust Move Semantics | [#36-dynamicimage-move-semantics-in-rust](#36-dynamicimage-move-semantics-in-rust) |
| 3.7 ML Model Memory Lifecycle | [#37-python-ml-model-memory-lifecycle](#37-python-ml-model-memory-lifecycle) |
