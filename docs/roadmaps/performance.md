# Performance Roadmap — Compute, Memory, and I/O

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [✅ §3.10 Test Suite Process Freeze — Root Cause Analysis](#-310-test-suite-process-freeze-root-cause-analysis)
- [✅ §3.11 Session-Level ThreadPoolExecutor Pool](#-311-session-level-threadpoolexecutor-pool)
- [✅ §3.12 pytest-xdist Worker Isolation](#-312-pytest-xdist-worker-isolation)
- [✅ §3.13 conftest.py Overhead Reduction](#-313-conftestpy-overhead-reduction)
- [✅ §3.14 Heavy-Library Import Isolation](#-314-heavy-library-import-isolation)
- [✅ §3.15 Heavy-Library Import Isolation — Non-animation Modules](#-315-heavy-library-import-isolation--non-animation-modules)
- [§3.1 Rust Streaming Image Merger](#31-rust-streaming-image-merger)
- [§3.2 ASP Render Stage GPU Acceleration](#32-asp-render-stage-gpu-acceleration)
- [§3.3 BiRefNet Inference Batching](#33-birefnet-inference-batching)
- [§3.4 Database Query Optimisation](#34-database-query-optimisation)
- [§3.5 WebDriver Lifecycle Management](#35-webdriver-lifecycle-management)
- [§3.6 DynamicImage Move Semantics in Rust](#36-dynamicimage-move-semantics-in-rust)
- [§3.7 Python ML Model Memory Lifecycle](#37-python-ml-model-memory-lifecycle)
- [Effort × Impact Matrix](#effort--impact-matrix)
- [Anchor Index](#anchor-index)

---

## Implementation Timeline

> **Legend** — *Node fill:* bug fix (red) · infrastructure (cyan) · performance (orange) · augmentation (violet) · refactor (teal) — *Node border:* ✅ complete (green, thick) · ⬜ planned (slate, thin) — *Edges:* `==>` critical blocking dependency · `-->` sequential dependency · `---` complements

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

    subgraph SHIPPED["✅ Test Infrastructure (§3.10–§3.15)"]
        S310["§3.10 Test Suite Freeze\nRoot Cause Analysis"]:::fix:::done
        S311["§3.11 Session-Level\nThreadPoolExecutor Pool"]:::fix:::done
        S312["§3.12 pytest-xdist\nWorker Isolation"]:::infra:::done
        S313["§3.13 conftest.py\nOverhead Reduction"]:::perf:::done
        S314["§3.14 Heavy-Library\nImport Isolation"]:::infra:::done
        S315["§3.15 Import Isolation —\nNon-animation Modules"]:::augment:::done
    end

    subgraph PLANNED["⬜ Runtime Performance (§3.1–§3.7)"]
        P31["§3.1 Rust Streaming\nImage Merger"]:::perf:::planned
        P32["§3.2 ASP Render Stage\nGPU Acceleration"]:::perf:::planned
        P33["§3.3 BiRefNet\nInference Batching"]:::augment:::planned
        P34["§3.4 Database Query\nOptimisation"]:::perf:::planned
        P35["§3.5 WebDriver Lifecycle\nManagement"]:::fix:::planned
        P36["§3.6 DynamicImage Move\nSemantics in Rust"]:::refactor:::planned
        P37["§3.7 Python ML Model\nMemory Lifecycle"]:::perf:::planned
    end

    %% Test infrastructure causal chain
    S310 ==> S311
    S310 ==> S312
    S310 ==> S313
    S310 ==> S314
    S314 --> S315

    %% Test suite parallelism siblings
    S311 --- S312

    %% Runtime performance dependencies
    P36 --> P31
    P32 --> P33
    P33 --> P37
    P34 --- P35

    %% Cross-group complements
    P33 --- P32
    P31 --- P36
```

*Node fill encodes element type (red = bug fix, cyan = infrastructure, orange = performance, violet = augmentation, teal = refactor). Node border encodes status (thick green = complete, thin slate = planned). Bold `==>` edges are critical blocking dependencies; `-->` is sequential ordering; `---` is a complementary relationship.*

---

## How to Use This Document

Each section describes a performance bottleneck, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping. Items tagged **⚠ CRITICAL** represent confirmed system-freeze root causes that must be resolved before running the full test suite.

---

## ✅ §3.10 Test Suite Process Freeze: Root Cause Analysis {: #-310-test-suite-process-freeze-root-cause-analysis }

> **Severity: CRITICAL — ALL ROOT CAUSES FIXED** — Running `pytest backend/test/animation/ --skip-gpu` is now safe (917 pass). `pytest backend/test/` (all modules) requires §3.15 non-animation audit to be complete. Root causes identified 2026-06-18; all fixed by 2026-06-18.

### Root Cause #1 — `from diffusers import DiffusionPipeline` at module level in `anim_fill.py` ✅ FIXED

**What happens:** `compositing.py` imports `anim_fill.py` at module level (line 29: `from .anim_fill import _generate_canonical_cel`). Until S140, `anim_fill.py` had `from diffusers import DiffusionPipeline` as an unconditional top-level import. This means importing `compositing.py` (which `test_compositing.py` does at collection time) triggers the full HuggingFace diffusers import chain:
- `diffusers` → `transformers` → `tokenizers` (Rust/Rayon thread pool, up to 24 threads on i9)
- `transformers` → `accelerate`, `safetensors`, `huggingface_hub`
- Estimated RAM cost at import time: **800 MB – 1.5 GB before any test runs**
- Tokenizers' Rayon pool spawns `num_cpus` threads. `TOKENIZERS_PARALLELISM=false` suppresses the parallelism but not the pool creation.

**Fix applied (S140):** `from diffusers import DiffusionPipeline` moved inside `_load_tooncrafter()`. `torch` import in `anim_fill.py` wrapped in `try/except ImportError`. `compositing.py` duplicate imports (lines 29–32) deduplicated to single import.

### Root Cause #2 — Module-level ML model singletons never evicted across test session ✅ FIXED

**What happens:** Three module-level singleton caches accumulate VRAM across the entire test session:
- `_DINOV2_CACHE[device]` in `frame_selection.py` — `TestDINOv2Features::test_identical_images_low_cosine_distance` calls `torch.hub.load("facebookresearch/dinov2", "dinov2_vits14")`, loading ~300 MB into VRAM. The singleton persists in VRAM for the remaining 900+ tests.
- `_SEARAFT_SINGLETON` in `fg_register.py` — if ptlflow is installed, `_dense_flow()` loads SEA-RAFT (~150 MB VRAM). Stays for the session.
- `_VGG19_SINGLETON` in `fg_register.py` — VGG19 partial (~500 MB VRAM).
- `_TC_PIPELINE` in `anim_fill.py` — ToonCrafter pipeline (**3.5–10 GB VRAM**) if any test triggers `_generate_canonical_cel` for real.

**The `resource_cleanup` autouse fixture** calls `torch.cuda.empty_cache()` after each test — this frees **unoccupied** CUDA memory allocations but does **not** evict model weights that are still referenced by the module-level dictionaries. Total VRAM pinned after worst-case collection: ~12+ GB.

**Fixes applied:**
- `TestDINOv2Features` marked `@pytest.mark.gpu` + `@pytest.mark.forked` — runs in an isolated subprocess; VRAM reclaimed by OS on subprocess exit (§3.12B).
- `TestComputeRlhfScore` marked `@pytest.mark.gpu` — can be excluded from CI runs via `--skip-gpu`.
- `--skip-gpu` CLI flag added to `conftest.py` — skips all `@pytest.mark.gpu` tests at collection time for fast non-GPU runs.
- Session-end singleton teardown (`clear_ml_singletons`) frees all singletons when the full session completes.

### Root Cause #3 — `ThreadPoolExecutor` spawned per `_composite_foreground` call across 311 tests ✅ FIXED

**What happens:** `_composite_foreground` in `compositing.py` creates `ThreadPoolExecutor(max_workers=min(N-1, 4))` on each call. `test_compositing.py` has 311 test functions, ~20 of which call `_composite_foreground` directly. Each pool creation:
- Calls `pthread_create()` (Linux) for up to 4 threads
- Each thread initialises its Python frame stack and GIL state
- Pool `__exit__` calls `thread.join()` and `pthread_join()` for all workers

This creates ~1,200 thread lifecycle calls during the test run. Under rapid sequential creation, Linux's CFS scheduler stalls while waiting for `pthread_create()` kernel locks to settle, causing visible system unresponsiveness on high-load CPUs.

**Fix applied:** See §3.11 — module-level `_SEAM_POOL` singleton + `_get_seam_pool()` in `compositing.py`.

### Root Cause #4 — `gc.collect()` called 931 times via autouse fixture ✅ FIXED

**What happens:** `resource_cleanup` is `autouse=True` in `conftest.py`, calling `gc.collect()` after every test. Python's cyclic GC traverses the entire reachable object graph. After Root Cause #1 is fixed, the remaining object graph is small. But if diffusers/transformers are loaded, their module globals (thousands of Python objects: classes, partial functions, closures) are traversed each time.
- Estimated cost with ML libraries loaded: 10–100 ms per `gc.collect()` call
- 931 tests × 50 ms = ~46 seconds of pure GC overhead, and intermittent GIL hold-time spikes

**Fix applied:** See §3.13A — `resource_cleanup` scope raised to `module` (931 → ~19 GC calls). CUDA cleanup gated behind `ASP_TEST_CUDA_CLEANUP=1`.

### Root Cause #5 — No process isolation: all 931 tests share one Python process ✅ FIXED

**What happens:** Because there is no `pytest-xdist` and no process-per-test isolation, every singleton loaded by test #1 stays alive for test #931. Memory fragmentation accumulates across the full session. On Linux, glibc's `malloc` keeps freed `mmap()` regions in its pool for reuse, causing RSS to climb monotonically throughout the session. A process that starts at 500 MB RSS after import can reach 8–12 GB RSS by test #900.

**Fixes applied:**
- `pytest-xdist` + `pytest-forked` installed.
- Parallel mode verified: `pytest backend/test/animation/ -n auto --dist=worksteal --skip-gpu` passes with same failure count, multiple independent worker processes each with bounded RSS.
- GPU tests isolated with `@pytest.mark.forked` (subprocess) or skipped via `--skip-gpu`.
- `pyproject.toml` documents the recommended invocations — addopts is intentionally empty (parallel execution is opt-in).

---

## ✅ §3.11 Session-Level ThreadPoolExecutor Pool {: #-311-session-level-threadpoolexecutor-pool }

> **Status: IMPLEMENTED** — Module-level `_SEAM_POOL` singleton in `compositing.py`. Zero thread churn after first call.

### Problem

`_composite_foreground` creates a new `ThreadPoolExecutor(max_workers=min(N-1, 4))` on every call. With 311 compositing tests each invoking `_composite_foreground` (20 directly + indirect via `AnimeStitchPipeline`), this generates thousands of `pthread_create`/`pthread_join` kernel calls in rapid succession. On Linux, `pthread_create` acquires `libpthread`'s global lock; under rapid fire, this lock becomes a serialisation bottleneck across all CPU cores.

### Options

**A — Module-level shared pool with lazy init [Quick Win]**
```python
_SEAM_POOL: Optional[concurrent.futures.ThreadPoolExecutor] = None
def _get_seam_pool(n_workers: int = 4) -> concurrent.futures.ThreadPoolExecutor:
    global _SEAM_POOL
    if _SEAM_POOL is None:
        _SEAM_POOL = ThreadPoolExecutor(max_workers=n_workers)
    return _SEAM_POOL
```
`_composite_foreground` calls `_get_seam_pool()` instead of creating a new pool. Pool lives for the process lifetime.
- Pros: Zero thread churn after the first call. Trivial change.
- Cons: Pool size is fixed at first call. Shared state between pipeline runs (acceptable).

**B — `concurrent.futures.ProcessPoolExecutor` for heavy seam cuts [Research]**
For seam DP on large canvases (>4K), replace thread pool with process pool. Each process has its own GIL; true parallelism on CPU-bound NumPy paths.
- Pros: Eliminates GIL contention on dense NumPy operations.
- Cons: IPC overhead for NumPy array serialisation. Cannot share module-level caches. Fork-after-CUDA-init deadlock risk — must set `multiprocessing.set_start_method("spawn")` before CUDA initialisation.

**C — Synchronous seam cut with vectorised NumPy [Quick Win]**
The `_seam_cut()` DP forward pass already uses `scipy.ndimage.minimum_filter1d` (vectorised). The main benefit of the thread pool was computing N-1 seam costs concurrently. For small frame counts (N ≤ 5), sequential is nearly as fast as parallel. Gate the ThreadPoolExecutor on `N-1 >= 4`.
- Pros: Avoids thread pool entirely for the common N=2 or N=3 case.
- Cons: Loses parallelism for large N.

**Recommendation:** A immediately — zero-cost fix. C as a secondary safeguard for small N. B is a future research item.

**Implemented:** Option A. `_get_seam_pool()` returns the module-level singleton; `_composite_foreground` uses `_pool.map()` directly without context-manager teardown. `clear_ml_singletons` session fixture calls `_SEAM_POOL.shutdown(wait=False)` at session end.

---

## ✅ §3.12 pytest-xdist Worker Isolation {: #-312-pytest-xdist-worker-isolation }

> **Status: All three options implemented.** C (singleton teardown session fixture), B (pytest-forked on DINOv2), A (pytest-xdist -n auto --dist=worksteal verified). GPU tests isolated with @pytest.mark.gpu + @pytest.mark.forked and skippable via --skip-gpu.

### Problem

Without process isolation, memory freed by test N is still resident in RSS (glibc malloc pool). ML singletons loaded by `TestDINOv2Features` (test ~250 of 931) pollute the VRAM and CPU caches for all subsequent 680 tests. A single process runs from 500 MB to 8–12 GB RSS over the course of the session.

### Options

**A — `pytest-xdist` with `-n auto` [Medium effort]**
```bash
pip install pytest-xdist
pytest backend/test/ -n auto
```
`pytest-xdist` forks N worker processes (one per CPU core). Each worker handles a subset of tests; when a worker process exits, its OS resources (RAM, VRAM-backed IPC handles) are fully reclaimed by the kernel.
- Caveat: CUDA contexts cannot be shared between processes. Tests that use CUDA must use `pytest.mark.cuda` + `--forked` worker mode (one fork per test).
- Caveat: `conftest.py` autouse fixtures still apply inside each worker.
- Pros: RSS is bounded per worker. Singletons reset between workers. Parallel execution cuts wall time by N×.
- Cons: Session-scoped fixtures are serialised. PostgreSQL tests need a shared test DB. Requires auditing fixture scopes.

**B — `pytest-forked` for model-loading tests [Quick Win]**
```bash
pip install pytest-forked
```
Mark only model-loading tests with `@pytest.mark.forked`. Each marked test runs in its own subprocess; the subprocess exits and OS reclaims all resources.
```python
@pytest.mark.forked
class TestDINOv2Features: ...
```
- Pros: Surgical isolation. Non-GPU tests are unaffected.
- Cons: Fork-after-CUDA requires `CUDA_VISIBLE_DEVICES=""` in the child or `spawn` start method.

**C — Explicit singleton teardown in session-scoped fixture**
```python
@pytest.fixture(scope="session", autouse=True)
def clear_ml_singletons():
    yield
    import backend.src.animation.frame_selection as fs
    import backend.src.animation.fg_register as fgr
    for k in list(fs._DINOV2_CACHE.keys()):
        model, _ = fs._DINOV2_CACHE.pop(k)
        if model is not None:
            del model
    if fgr._SEARAFT_SINGLETON is not None:
        del fgr._SEARAFT_SINGLETON
        fgr._SEARAFT_SINGLETON = None
    import torch; torch.cuda.empty_cache()
```
- Pros: No new dependency. Targeted cleanup.
- Cons: Only frees singletons at session end — doesn't help with mid-session VRAM accumulation.

**Recommendation:** C first (no dependency), then B to isolate model-loading tests. A for maximum isolation once fixture scopes are audited.

**Implemented:** All three options.
- **C:** `clear_ml_singletons` (autouse, scope=session) tears down all five ML singletons + seam pool at session end.
- **B:** `TestDINOv2Features` marked `@pytest.mark.forked` — runs each test in an isolated subprocess; `pytest-forked` 1.6.0 installed.
- **A:** `pytest-xdist` 3.8.0 installed. `pytest -n auto --dist=worksteal --skip-gpu` verified on animation suite; same 6 pre-existing failures, correct skip counts.

---

## ✅ §3.13 conftest.py Overhead Reduction {: #-313-conftestpy-overhead-reduction }

> **Status: IMPLEMENTED** — `resource_cleanup` scope raised to `module`. GC calls reduced 931 → ~19. CUDA cleanup gated behind `ASP_TEST_CUDA_CLEANUP=1`.

### Problem

The `resource_cleanup` autouse fixture (scope=`function`) runs after all 931 tests. `gc.collect()` traverses the entire Python heap, which after diffusers/transformers import can include millions of objects. `torch.cuda.empty_cache()` triggers a CUDA driver ioctl, causing a kernel-mode context switch on every test. Combined, this overhead exceeds the runtime of many short tests.

### Options

**A — Raise `resource_cleanup` scope to `module` [Quick Win]**
```python
@pytest.fixture(autouse=True, scope="module")
def resource_cleanup():
    yield
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
```
GC and CUDA cache flush run once per test module (19 modules) instead of 931 times. For non-GPU test modules, `torch.cuda.is_available()` returns False quickly.
- Pros: 50× reduction in GC calls (931 → 19). Zero code changes to tests.
- Cons: Memory is not freed between tests within a module. Acceptable since individual tests are small.

**B — Use `@pytest.mark.gc_heavy` for memory-intensive tests**
Only run `gc.collect()` after tests that are known to allocate large objects. Mark with a custom marker:
```python
@pytest.mark.gc_heavy
def test_five_frames_parallel_path_completes(self): ...
```
Fixture checks `request.node.get_closest_marker("gc_heavy")`.
- Pros: Surgical. GC only when needed.
- Cons: Requires auditing and marking tests.

**C — Remove `gc.collect()` entirely; rely on CPython refcounting**
CPython's reference counting frees most objects immediately when their refcount hits zero. The cyclic GC is only needed for circular references. Most test objects (numpy arrays, simple dicts) have no cycles and are freed by refcounting. Remove `gc.collect()` from the fixture; only keep `torch.cuda.empty_cache()` at module scope.
- Pros: Maximum test throughput. No GC pauses.
- Cons: Circular reference leaks will accumulate (rare in well-written code). Must verify no test objects have intentional cycles.

**D — Conditional CUDA cleanup**
Guard `torch.cuda.empty_cache()` behind `os.environ.get("ASP_TEST_CUDA_CLEANUP", "0") != "0"`. Enable only when running GPU-heavy test classes.
- Pros: Eliminates CUDA ioctl overhead for 95%+ of test runs.
- Cons: Must remember to enable for GPU tests.

**Recommendation:** A immediately. C as a follow-up after verifying no cyclic test objects. D for GPU-gated runs.

**Implemented:** Options A + B + C + D (2026-06-18):
- **A:** Scope raised to `module` (931 → ~19 GC calls). ✅
- **B:** `gc_heavy_cleanup` function-scoped autouse fixture added to `conftest.py`; checks `request.node.get_closest_marker("gc_heavy")` and calls `gc.collect()` only when set. Marker applied to `TestCompositeForeground` and `TestParallelSeamPrecompute` (compositing), all of `test_filter_edges.py` (480×640 frames), and `TestNdarrayCodec::test_large_array_is_skipped` (16 MB array). ✅
- **C:** `gc.collect()` removed from `resource_cleanup`; only CUDA flush remains. CPython refcounting handles non-cyclic test objects immediately; no cyclic references identified in the animation suite. GC calls now = number of `@pytest.mark.gc_heavy` tests (~40) rather than 931 (per function) or 19 (per module). ✅
- **D:** CUDA flush gated behind `ASP_TEST_CUDA_CLEANUP=1`. ✅

---

## ✅ §3.14 Heavy-Library Import Isolation {: #-314-heavy-library-import-isolation }

> **Status: IMPLEMENTED** — Remaining unconditional heavy imports patched. See below.

### Problem

The `compositing.py` module-level import chain (fixed in S140) is the highest-impact example of a broader pattern: production modules importing optional heavy libraries unconditionally, causing those libraries to load at test collection time even when the tests never exercise the code path that needs them.

Remaining risk areas after S140:
- `fg_register.py` lines 43–63: `import torch`, `import ptlflow`, `import torchvision.models` in `try/except` blocks — acceptable (guarded), but torch is loaded unconditionally even when ptlflow is absent.
- `bench_anime_stitch.py`: `_get_reward_model()` lazy singleton — acceptable.
- `pipeline.py`: `from .bg_complete import _propainter_complete_frames` — `bg_complete.py` may import ProPainter-related libraries at module level.

### Options

**A — Audit and lazy-ify all top-level heavy imports [Quick Win per module]**
For each `backend/src/animation/` module, verify that any library with known heavy import cost (torch, diffusers, transformers, ptlflow, torchvision, skimage, scipy) is either:
1. Imported inside the function that first uses it, OR
2. Wrapped in `try/except ImportError` so that it degrades gracefully, OR
3. Documented as a known mandatory dependency in `pyproject.toml [project.dependencies]`.

**B — `importtime` profiling in CI**
Add a CI step: `python -m pytest --collect-only backend/test/animation/` with `PYTHONPROFILEIMPORTTIME=1` (Python 3.11 startup profiling). Compare import time before/after changes.
- Pros: Automated regression detection.
- Cons: CI-only; doesn't help local development.

**C — `lazy-object-proxy` for heavy module attributes**
Use `lazy-object-proxy` to defer attribute resolution until first access:
```python
import lazy_object_proxy
ssim_fn = lazy_object_proxy.Proxy(lambda: __import__("skimage.metrics", ...).structural_similarity)
```
- Pros: Zero change to call sites.
- Cons: Additional dependency. Proxy adds slight per-call overhead.

**Recommendation:** A for immediate wins module-by-module. B as a CI regression gate. C only if A produces too many call-site changes.

**Implemented:** Option A + B — comprehensive audit of all `backend/src/animation/` modules complete (2026-06-18):

**Phase 1 (S140 + previous session):**
- `compositing.py`: `import torch as _tc_torch` → `try/except ImportError`.
- `bg_complete.py`: `import torch` → `try/except ImportError`.
- `fg_register.py`: torch already guarded — no change.

**Phase 2 (§3.14 full audit):**
- `masking.py`: Deleted 18-line "Relocated Nested Imports" block; SAM-2 + grounding imports fully lazy.
- `rendering.py`: sklearn KMeans → lazy function-level import.
- `frame_selection.py`: Deleted 9-line "Relocated Nested Imports" block; torch/torchvision/PIL wrapped; BiRefNetWrapper lazy.
- `matching.py`: `import torch` → `try/except ImportError`.
- `pipeline.py`: `import torch` + `from PIL import Image` → `try/except ImportError`.

**Phase 3 (wrapper + __init__ sweep — current):**
- `pipeline.py`: All 5 heavy model-wrapper try/except blocks (BiRefNetWrapper, LoFTRWrapper, EfficientLoFTRWrapper, ALIKEDLightGlueWrapper, unused AnimeStitchNet) replaced with `importlib.util.find_spec()` probes. All 4 classes imported lazily at instantiation sites. "Relocated Nested Imports" block cleaned up (deduplicated; JamMaWrapper lazy).
- `backend/src/models/__init__.py`: All 8 eager wrapper re-exports removed; only base utilities remain. Previously this caused EVERY import of any wrapper to trigger the full chain (birefnet → transformers + aliked → kornia + eloftr → transformers).
- `fg_register.py`: `torchvision.models` (464 ms) moved from try/except module-level into `_get_vgg19_feat()`.
- `backend/scripts/check_import_times.py`: §3.14B CI regression gate — measures all 14 animation modules in subprocesses, flags any exceeding 1.5 s net above baseline. Run: `python backend/scripts/check_import_times.py --ci`.

**Result (Phase 3):** All 14 animation modules pass the 1.5 s threshold (net cost 0.67–0.80 s, down from 1.6–2.4 s). 917 animation tests pass (0 new failures).

---

## ✅ §3.15 Heavy-Library Import Isolation — Non-animation Modules {: #-315-heavy-library-import-isolation--non-animation-modules }
<a id="-315-heavy-library-import-isolation-non-animation-modules"></a>

> **Status: IMPLEMENTED** — `image_merger.py` and `vault_manager.py` patched. `check_import_times.py` extended to cover core modules. All 16 tracked modules pass the 1.5 s threshold.

### Problem

§3.14 fixed all 14 `backend/src/animation/` modules but left two non-animation source modules with the same "Relocated Nested Imports" pattern, discovered when auditing the non-animation test files in `backend/test/`:

- **`backend/src/core/image_merger.py`** — six unconditional model-wrapper imports at module level:
  ```python
  from backend.src.models.siamese_network import SiameseModelLoader
  from backend.src.models.gan_wrapper import GanWrapper
  from backend.src.models.birefnet_wrapper import BiRefNetWrapper   # → transformers (~800ms)
  from backend.src.models.basic_wrapper import BaSiCWrapper
  from backend.src.models.loftr_wrapper import LoFTRWrapper          # → kornia (~168ms)
  from backend.src.animation import AnimeStitchPipeline                   # → entire animation pipeline (~800ms)
  ```
  `test_image_merger_ml.py` imports `ImageMerger` at collection time, triggering all six. Total estimated cost: ~3 s above baseline — would have been flagged as SLOW by the CI gate if core modules were included.

- **`backend/src/core/vault_manager.py`** — `import jpype` unconditionally at module level:
  ```python
  import jpype
  from jpype.types import JArray, JChar
  ```
  `test_java_vault_manager.py` imports `VaultManager` at collection time. If jpype is installed, this triggers JVM path resolution. If jpype is absent, it raises `ImportError` crashing collection of all tests that run after it in the same worker.

- **`backend/scripts/check_import_times.py`** — only covered animation modules; core modules were invisible to the CI gate.

### Options

**A — Lazy wrapper imports in `_get_*()` [Quick Win]**
Same pattern as §3.14 Phase 3: replace module-level imports with `find_spec()` probes + lazy `from ... import` inside each `_get_*()` method and `perfect_stitch()`.

**B — try/except ImportError for `jpype` [Quick Win]**
Wrap `import jpype; from jpype.types import ...` in `try/except ImportError`, setting module-level `_JPYPE_OK = False` when absent.

**C — Extend CI gate to cover core modules [Quick Win]**
Add `CORE_MODULES` list to `check_import_times.py`; fold into the same measurement loop.

**Recommendation:** All three together — zero friction, same approach as §3.14.

**Implemented:** Options A + B + C (2026-06-18):
- **A:** `image_merger.py` — 6 unconditional imports removed. `find_spec()` probes for `transformers` (`_BIREFNET_OK`) and `kornia` (`_LOFTR_OK`). `try/except ImportError` for BaSiCWrapper, GanWrapper, SiameseModelLoader (lightweight). Lazy `from ... import` inside `_get_gan()`, `_get_birefnet()`, `_get_loftr()`, `_get_siamese()`, and `perfect_stitch()`. "Relocated Nested Imports" comment block removed.
- **B:** `vault_manager.py` — `import jpype` + `from jpype.types import JArray, JChar` wrapped in `try/except ImportError`; `_JPYPE_OK` flag set.
- **C:** `check_import_times.py` — `CORE_MODULES` list added; `run()` extended to measure both groups; final count now 16 modules.

**Result:** `image_merger` net cost 0.50 s (was ~3+ s); `vault_manager` net cost 0.47 s. All 16 modules pass the 1.5 s threshold. 8 image_merger + vault_manager tests still pass.

---

---

## 3.1 C++ Streaming Image Merger

**Pain point:** `base/src/core/merger.cpp` loads all input images into a `std::vector<cv::Mat>` before compositing. Merging 100 × 4K images temporarily consumes 2–4 GB of RAM.

### Options

**A — Two-pass streaming (sequential)**
Pass 1: read image headers only (parse width/height without decoding pixels — use `cv::imdecode` header probe or `libpng`/`libjpeg` dimension queries). Compute final canvas dimensions from all headers. Allocate output buffer. Pass 2: decode each image one at a time, blit to canvas, release immediately.
- Peak RAM: 1 image at a time (~30 MB for 4K RGBA) + output buffer (~200 MB for a 10K panorama).
- Pros: Near-minimal RAM usage during processing. No new dependencies.
- Cons: Two filesystem passes. Slower on spinning disks; acceptable on NVMe.

**B — OpenMP-parallel with bounded semaphore**
Keep parallel load but limit concurrent live images to `N_cores` using a `std::counting_semaphore` (C++20) or `std::mutex`-guarded counter. Each thread acquires a permit before loading, releases after blitting.
- Peak RAM: `N_cores × image_size` (e.g., 8 cores × 30 MB = 240 MB).
- Pros: Balances throughput vs memory. Better I/O pipeline utilisation than sequential.
- Cons: Non-trivial semaphore integration with OpenMP's work-sharing scheduler.

**C — Memory-mapped output buffer (mmap)**
Use POSIX `mmap()` (Linux/macOS) or `CreateFileMapping` (Windows) to map the output file directly into virtual memory. Each thread writes its strip directly to the mapped region; the OS flushes to disk lazily.
- Pros: Zero extra RAM for the output buffer. Particularly useful for panoramas >10K px.
- Cons: Output file must be pre-allocated to its final size. Random-write performance depends on OS page eviction policy.

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

**B — C++ RAII guard**
In the pybind11 bindings, use a stack-allocated RAII wrapper whose destructor calls `quit()`. Handles C++ exceptions as well as normal exits.
- Pros: Handles C++-side exceptions that Python's `try/finally` doesn't see.
- Cons: Only applies to C++-initiated crawls. pybind11 already translates C++ exceptions to Python exceptions at the boundary.

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

## Effort × Impact Matrix {: #effort--impact-matrix }

*Effort* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks
*Impact* — **Low**: marginal · **Medium**: measurable improvement for targeted workloads · **High**: significant throughput or memory gain · **Very High**: unlocks new scale or eliminates blocking bottleneck

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | — | §3.4B prepared statements · §3.5A Selenium context manager · §3.6A DynamicImage move ownership · §3.7A explicit model unload · §5.7A uv lock | §3.4D HNSW index tuning · §3.4C partial index on path · ~~**⚠§3.11A session-level ThreadPoolExecutor**~~ ✅ · ~~**⚠§3.13A module-scope gc.collect()**~~ ✅ · ~~**⚠§3.14A lazy heavy imports**~~ ✅ · ~~**⚠§3.12B pytest-forked for model tests**~~ ✅ | — |
| **Medium (1d–1w)** | §3.9 SI-FID metric | §3.4A psycopg3 async pool · §3.4E materialized view · §3.7B LRU model cache · ~~**⚠§3.12C singleton teardown fixture**~~ ✅ · ~~**⚠§3.12A pytest-xdist full isolation**~~ ✅ | §3.3C dynamic BiRefNet batching · §3.5D Playwright migration | — |
| **High (1–2w)** | — | §3.4F table partitioning | §3.1A two-pass streaming merger · §3.2A GPU median (PyTorch CUDA) | — |
| **Very High (2w+)** | — | — | §5.5C Rust AES-256-GCM vault (eliminates JVM + libstdc++ conflicts) | — |

---

## Anchor Index

| Section | Anchor |
|---------|--------|
| **✅ 3.10 Test Suite Freeze Root Cause Analysis** | [#-310-test-suite-process-freeze-root-cause-analysis](#-310-test-suite-process-freeze-root-cause-analysis) |
| **✅ 3.11 Session-Level ThreadPoolExecutor** | [#-311-session-level-threadpoolexecutor-pool](#-311-session-level-threadpoolexecutor-pool) |
| **✅ 3.12 pytest-xdist Worker Isolation** | [#-312-pytest-xdist-worker-isolation](#-312-pytest-xdist-worker-isolation) |
| **✅ 3.13 conftest.py Overhead Reduction** | [#-313-conftestpy-overhead-reduction](#-313-conftestpy-overhead-reduction) |
| **✅ 3.14 Heavy-Library Import Isolation (animation)** | [#-314-heavy-library-import-isolation](#-314-heavy-library-import-isolation) |
| **✅ 3.15 Heavy-Library Import Isolation (core)** | [#-315-heavy-library-import-isolation-non-animation-modules](#-315-heavy-library-import-isolation-non-animation-modules) |
| 3.1 Streaming Image Merger | [#31-rust-streaming-image-merger](#31-rust-streaming-image-merger) |
| 3.2 GPU Render Acceleration | [#32-asp-render-stage-gpu-acceleration](#32-asp-render-stage-gpu-acceleration) |
| 3.3 BiRefNet Batching | [#33-birefnet-inference-batching](#33-birefnet-inference-batching) |
| 3.4 Database Optimisation | [#34-database-query-optimisation](#34-database-query-optimisation) |
| 3.5 WebDriver Lifecycle | [#35-webdriver-lifecycle-management](#35-webdriver-lifecycle-management) |
| 3.6 Rust Move Semantics | [#36-dynamicimage-move-semantics-in-rust](#36-dynamicimage-move-semantics-in-rust) |
| 3.7 ML Model Memory Lifecycle | [#37-python-ml-model-memory-lifecycle](#37-python-ml-model-memory-lifecycle) |

---

## Document History

*Last updated: 2026-06-18. §3.10–§3.15 fully ✅. §3.15 non-animation import audit: image_merger.py (6 unconditional model imports → lazy) + vault_manager.py (jpype → try/except) + check_import_times.py extended to 16 modules (all pass 1.5 s threshold). §3.10–§3.14 complete from prior sessions. All Tier 1–5 RAM reduction items are fully implemented (✅). These are the next-generation opportunities.*
