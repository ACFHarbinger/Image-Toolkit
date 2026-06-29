# Rust → C++ Migration Roadmap: `base/` (formerly `batch/`)

**Status: COMPLETE — All 12 phases done. Rust base retired to `archive/rust/`. All 27 Python-exposed functions ported and verified.**

**Rename complete (Phase 7):** `batch/` has been renamed `base/`. The Rust PyO3 module has been archived
to `archive/rust/`. `import base` now resolves to the C++ pybind11 extension directly.

---

## Motivation

The Rust `base/` module provides the performance-critical Python extension layer:

- Parallel image batch loading and thumbnail generation (`load_image_batch`)
- Recursive filesystem scanning (`scan_files`)
- Parallel video thumbnail extraction (`extract_video_thumbnails_batch`)
- Encrypted vector database operations (`insert_listing_secure`, `hybrid_search_secure`, etc.)
- Zero-copy Apache Arrow bulk export (`fetch_listings_as_arrow_pointers`)
- HTTP request sequencing (`run_web_requests_sequence`)
- Pure Rust math library (`base/src/math/`) for the analytics roadmap (no Python bindings)

The project already has a mature C++ extension infrastructure (`batch/`) with:

- pybind11 2.11+, zero-copy numpy↔cv::Mat converters, GIL management patterns
- OpenCV 4.8+, Eigen3, OpenMP, optional CUDA
- CMakeLists.txt, `just build-batch`, parity test framework

Migrating `base/` into this infrastructure consolidates the native extension layer into a single C++
codebase with unified build tooling, eliminates the Rust/PyO3 ABI dependency, and gives the math library
access to Eigen3 and OpenCV.

The `thirtyfour`-based web crawlers (`base/src/web/crawlers/`) are **not migrated** — browser automation
is highest-level in Python (Selenium Python API is the canonical interface); the C++ port offers no
real benefit and would require a headless browser C++ binding with poor ecosystem support.

The cloud sync wrappers (`base/src/web/cloud/`) are thin REST API clients. These remain in Python.

---

## Architecture Overview

### Current architecture

```
Python
  ├── import base          (PyO3/Rayon — Rust, ABI-stable py311)
  │     ├── load_image_batch()
  │     ├── scan_files()
  │     ├── extract_video_thumbnails_batch()
  │     ├── run_web_requests_sequence()
  │     ├── insert_listing_secure() / hybrid_search_secure() / …
  │     └── fetch_listings_as_arrow_pointers()
  └── import batch         (pybind11 — C++, OpenCV/Eigen/OpenMP)
        ├── matching, seam, compositing, canvas, …  (ASP pipeline)
        └── (11 submodules from asp_cpp_migration.md)
```

### Target architecture (after Phase 7 rename)

```
Python
  ├── import base          (pybind11 — C++, unified native extension)
  │     ├── image          ← load_image_batch, scan_files
  │     ├── video          ← extract_video_thumbnails_batch
  │     ├── web            ← run_web_requests_sequence
  │     ├── secret         ← insert_listing_secure / hybrid_search_secure / …
  │     ├── arrow          ← fetch_listings_as_arrow_pointers
  │     ├── matching, seam, compositing, canvas, …  (retained ASP submodules)
  │     └── math           ← Matrix, Graph, distance, stats, …  (no Python bindings)
  └── (Rust base/ retired to archive/base_rust/)
```

---

## Module Design

### Phase 2 — `batch::image` (image I/O + filesystem)

**Rust source:** `base/src/core/image_converter.rs`, `base/src/lib.rs` (`load_image_batch`, `scan_files`)

#### `load_image_batch`

Rust uses `rayon`, `image` crate, and `fast_image_resize` for INTER_AREA-quality thumbnail generation.
C++ replacement uses OpenCV + OpenMP:

```cpp
// batch/src/image/image_batch.cpp
#include <opencv2/opencv.hpp>
#include <pybind11/numpy.h>
#include <omp.h>

// Returns list of (path, thumbnail_ndarray, error_str) tuples.
// thumbnail_ndarray is HxWx3 uint8 (BGR); empty on error.
py::list load_image_batch_impl(
    const std::vector<std::string>& paths,
    int thumb_w, int thumb_h,
    bool keep_aspect)
{
    const int N = static_cast<int>(paths.size());
    std::vector<cv::Mat> thumbs(N);
    std::vector<std::string> errors(N);

    {
        py::gil_scoped_release release;
        #pragma omp parallel for schedule(dynamic)
        for (int i = 0; i < N; i++) {
            cv::Mat img = cv::imread(paths[i], cv::IMREAD_COLOR);
            if (img.empty()) {
                errors[i] = "imread failed";
                continue;
            }
            cv::Size target(thumb_w, thumb_h);
            if (keep_aspect) {
                double sx = (double)thumb_w / img.cols;
                double sy = (double)thumb_h / img.rows;
                double s  = std::min(sx, sy);
                target = cv::Size(
                    static_cast<int>(img.cols * s),
                    static_cast<int>(img.rows * s));
            }
            cv::resize(img, thumbs[i], target, 0, 0, cv::INTER_AREA);
        }
    }

    py::list result;
    for (int i = 0; i < N; i++) {
        py::tuple entry;
        if (thumbs[i].empty()) {
            entry = py::make_tuple(
                paths[i],
                py::none(),
                errors[i].empty() ? "unknown error" : errors[i]);
        } else {
            entry = py::make_tuple(
                paths[i],
                batch::array_from_mat(thumbs[i]),
                "");
        }
        result.append(entry);
    }
    return result;
}
```

**Python dispatch (in `base.py` wrapper):**

```python
_HAS_BASE_CPP = False
try:
    import batch as _batch_cpp
    _HAS_BASE_CPP = hasattr(_batch_cpp, "image")
except ImportError:
    pass

def load_image_batch(paths, thumb_w=256, thumb_h=256, keep_aspect=True):
    if _HAS_BASE_CPP:
        return _batch_cpp.image.load_image_batch(paths, thumb_w, thumb_h, keep_aspect)
    import base as _base_rust
    return _base_rust.load_image_batch(paths, thumb_w, thumb_h, keep_aspect)
```

#### `scan_files`

Rust uses `walkdir` + `rayon`. C++ uses `std::filesystem::recursive_directory_iterator` + OpenMP:

```cpp
std::vector<std::string> scan_files_impl(
    const std::string& root_dir,
    const std::vector<std::string>& extensions,
    bool recursive)
{
    namespace fs = std::filesystem;
    std::vector<std::string> all_paths;

    // Collect paths single-threaded (filesystem iteration is not thread-safe)
    auto it_fn = [&](auto&& it) {
        for (const auto& entry : it) {
            if (!entry.is_regular_file()) continue;
            std::string ext = entry.path().extension().string();
            std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
            for (const auto& e : extensions) {
                if (ext == e) { all_paths.push_back(entry.path().string()); break; }
            }
        }
    };

    if (recursive)
        it_fn(fs::recursive_directory_iterator(root_dir));
    else
        it_fn(fs::directory_iterator(root_dir));

    return all_paths;
}
```

---

### Phase 3 — `batch::video` (video thumbnails)

**Rust source:** `base/src/lib.rs` (`extract_video_thumbnails_batch`)

Rust uses `ffmpeg` CLI via `std::process::Command` + rayon. C++ uses OpenCV `VideoCapture` directly,
eliminating the subprocess dependency:

```cpp
// batch/src/video/video_batch.cpp
struct VideoThumbResult {
    std::string path;
    std::vector<cv::Mat> frames;  // one per requested timestamp
    std::string error;
};

VideoThumbResult extract_video_thumbnails_impl(
    const std::string& video_path,
    const std::vector<double>& timestamps_sec,
    int thumb_w, int thumb_h)
{
    VideoThumbResult result{video_path, {}, ""};
    cv::VideoCapture cap(video_path);
    if (!cap.isOpened()) {
        result.error = "VideoCapture failed to open: " + video_path;
        return result;
    }
    double fps = cap.get(cv::CAP_PROP_FPS);
    for (double ts : timestamps_sec) {
        cap.set(cv::CAP_PROP_POS_MSEC, ts * 1000.0);
        cv::Mat frame;
        if (!cap.read(frame)) { result.frames.emplace_back(); continue; }
        cv::Mat thumb;
        cv::resize(frame, thumb, cv::Size(thumb_w, thumb_h), 0, 0, cv::INTER_AREA);
        result.frames.push_back(std::move(thumb));
    }
    (void)fps;
    return result;
}

py::list extract_video_thumbnails_batch_impl(
    const std::vector<std::string>& paths,
    const std::vector<double>& timestamps_sec,
    int thumb_w, int thumb_h)
{
    const int N = static_cast<int>(paths.size());
    std::vector<VideoThumbResult> results(N);
    {
        py::gil_scoped_release release;
        #pragma omp parallel for schedule(dynamic)
        for (int i = 0; i < N; i++)
            results[i] = extract_video_thumbnails_impl(
                paths[i], timestamps_sec, thumb_w, thumb_h);
    }
    py::list out;
    for (auto& r : results) {
        py::list frames;
        for (auto& f : r.frames)
            frames.append(f.empty() ? py::object(py::none()) :
                          py::object(batch::array_from_mat(f)));
        out.append(py::make_tuple(r.path, frames, r.error));
    }
    return out;
}
```

---

### Phase 4 — `batch::secret` (secure vector database)

**Rust source:** `base/src/core/secure_vector_db.rs`

This is the most security-critical module. The Rust implementation provides:
- Argon2id KDF (OWASP params: 19 MB memory, 2 iterations, parallelism 1) via `argon2` crate
- SQLCipher page-level AES-256 encryption via `rusqlite` with `bundled-sqlcipher`
- `sqlite-vec` vector extension for cosine-similarity search
- `MemoryLockedKey`: `mlock()` + `zeroize::Zeroize` on drop
- Arrow FFI export for zero-copy bulk transfer (`fetch_listings_as_arrow_pointers`)

C++ replacement uses:

| Rust crate | C++ equivalent |
|---|---|
| `argon2` | `libsodium` `crypto_pwhash` (Argon2id, same OWASP params) |
| `rusqlite` + `bundled-sqlcipher` | SQLite3 C API + SQLCipher (link `libsqlcipher`) |
| `sqlite-vec` | `sqlite-vec` C loadable extension (`sqlite3_load_extension`) |
| `zeroize` | `sodium_memzero()` or `memset_s()` (C11) |
| `secrecy::Secret<T>` | Custom `LockedSecret<N>` wrapper with `mlock`/`munlock`/`sodium_memzero` |
| `arrow_array` / `arrow_data` / Arrow FFI | Apache Arrow C Data Interface (`ArrowArray` / `ArrowSchema` structs) |

```cpp
// batch/include/batch/secret/locked_secret.hpp
template <size_t N>
struct LockedSecret {
    uint8_t data[N];

    LockedSecret() { mlock(data, N); }
    ~LockedSecret() {
        sodium_memzero(data, N);
        munlock(data, N);
    }
    // Non-copyable
    LockedSecret(const LockedSecret&) = delete;
    LockedSecret& operator=(const LockedSecret&) = delete;
};

using DEK = LockedSecret<32>;

// Derive DEK from password using Argon2id (libsodium)
bool derive_dek(
    const std::string& password,
    const uint8_t* salt_32,   // 32-byte salt
    DEK& out_dek)
{
    return crypto_pwhash(
        out_dek.data, sizeof(out_dek.data),
        password.c_str(), password.size(),
        salt_32,
        2,                             // opslimit (iterations)
        19456ULL * 1024,               // memlimit (~19 MB)
        crypto_pwhash_ALG_ARGON2ID13
    ) == 0;
}
```

#### Arrow C Data Interface export

```cpp
// Zero-copy bulk export via Arrow C Data Interface (no Arrow C++ library needed)
// Caller receives raw pointers; pybind11 passes them to Python as integers.
// Python side uses pyarrow.RecordBatch._import_from_c(array_ptr, schema_ptr).
struct ArrowExport {
    ArrowArray  array;
    ArrowSchema schema;
};

py::tuple fetch_listings_as_arrow_pointers_impl(
    const std::string& db_path,
    const std::string& password)
{
    // … open db, build ArrowArray/ArrowSchema from query results …
    auto* export_ptr = new ArrowExport{};
    // populate export_ptr->array and export_ptr->schema …
    uintptr_t array_addr  = reinterpret_cast<uintptr_t>(&export_ptr->array);
    uintptr_t schema_addr = reinterpret_cast<uintptr_t>(&export_ptr->schema);
    return py::make_tuple(array_addr, schema_addr);
}
```

Python consumption (unchanged from Rust version):

```python
import pyarrow as pa
array_ptr, schema_ptr = batch.secret.fetch_listings_as_arrow_pointers(db_path, password)
record_batch = pa.RecordBatch._import_from_c(array_ptr, schema_ptr)
```

---

### Phase 5 — `batch::web` (HTTP request sequencing)

**Rust source:** `base/src/web/clients/web_requests.rs`

Rust uses `reqwest::blocking` with `serde_json`. C++ uses `cpp-httplib` (header-only, no CMake dep)
or `libcurl` (available everywhere):

```cpp
// batch/src/web/web_requests.cpp
// Uses cpp-httplib (header-only: https://github.com/yhirose/cpp-httplib)
#include "httplib.h"
#include <nlohmann/json.hpp>

std::string run_web_requests_sequence_impl(
    const std::string& config_json,
    std::function<void(const std::string&)> status_cb)
{
    auto config = nlohmann::json::parse(config_json);
    std::string base_url = config.value("base_url", "");
    // … iterate requests, call status_cb for progress events …
    return result_json.dump();
}
```

pybind11 binding wraps `status_cb` as a Python callable with GIL reacquire:

```cpp
py::str run_web_requests_sequence(
    const std::string& config_json,
    py::object callback_obj)
{
    auto cb = [&](const std::string& msg) {
        py::gil_scoped_acquire acquire;
        callback_obj.attr("on_status")(msg);
    };
    py::gil_scoped_release release;
    return run_web_requests_sequence_impl(config_json, cb);
}
```

**New CMake dependency** (header-only, auto-fetched via FetchContent):

```cmake
FetchContent_Declare(
    cpp-httplib
    GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
    GIT_TAG        v0.16.0
)
FetchContent_MakeAvailable(cpp-httplib)
```

---

### Phase 6 — `batch::math` (pure math library, no Python bindings)

**Rust source:** `base/src/math/` (linalg, graph, distance, stats, information, dim_reduce)

The math library has no Python bindings in Rust — it is used internally by the analytics roadmap phases
and by the ASP pipeline helpers (spanning-tree, UnionFind in `§1.1B`). C++ replacement is a header-only
library under `batch/include/batch/math/`, using Eigen3 (already a CMake dependency) where applicable:

| Rust module | C++ header | Eigen3 used |
|---|---|---|
| `linalg.rs` (Matrix, PCA via power iteration) | `math/linalg.hpp` | Yes (`Eigen::MatrixXd`, `SelfAdjointEigenSolver`) |
| `graph.rs` (Graph, BFS, DFS, Kruskal, SCC, topo) | `math/graph.hpp` | No |
| `distance.rs` (euclidean, cosine, hamming, etc.) | `math/distance.hpp` | No |
| `stats.rs` (mean, median, std_dev, pearson, z-score) | `math/stats.hpp` | No |
| `information.rs` (Shannon entropy, KL/JS, mutual info) | `math/information.hpp` | No |
| `dim_reduce.rs` (MDS, t-SNE affinities) | `math/dim_reduce.hpp` | Yes (`Eigen::MatrixXd`) |

These headers are included directly by other `batch/` source files — no pybind11 module registration needed.
The ASP pipeline submodules that use UnionFind (`bundle_adjust.cpp`, `spanning_tree.cpp`) include
`batch/math/graph.hpp` instead of duplicating the implementation.

---

### Modules NOT migrated

| Rust source | Reason |
|---|---|
| `base/src/web/crawlers/` (CrawlerBase, image crawlers, Danbooru, Gelbooru, etc.) | `thirtyfour` (Selenium) has no viable C++ equivalent with comparable ease-of-use. Browser automation stays in Python. |
| `base/src/web/cloud/` (Google Drive, OneDrive, Dropbox sync) | Thin REST wrappers over cloud SDK Python clients. No performance benefit. |
| `base/src/core/vault_manager.py`-adjacent legacy migration (`run_legacy_migration`) | One-shot migration helper; runs once per installation. Keep in Python. |

---

## Phasing

### ✅ Phase 1 — Build system & dispatch scaffolding

**Goal:** Wire new `batch::image`, `batch::video`, `batch::secret`, `batch::web`, `batch::math`
submodule stubs into CMakeLists.txt and establish the `_HAS_BASE_CPP` dispatch pattern.

**Tasks:**

1. Add submodule stubs to `batch/CMakeLists.txt`:
   ```cmake
   target_sources(batch PRIVATE
       src/image/image_batch.cpp
       src/video/video_batch.cpp
       src/secret/vault_db.cpp
       src/secret/locked_secret.cpp
       src/web/web_requests.cpp
   )
   ```
2. Create `batch/include/batch/math/` directory and header stubs.
3. Add `libsodium` CMake dependency (required for Phase 4):
   ```cmake
   find_package(PkgConfig REQUIRED)
   pkg_check_modules(SODIUM REQUIRED libsodium)
   target_link_libraries(batch PRIVATE ${SODIUM_LIBRARIES})
   ```
4. Add `cpp-httplib` via FetchContent (Phase 5, header-only, no link required).
5. Write the `_HAS_BASE_CPP` dispatch shim in `backend/src/utils/base_dispatch.py`.
6. All stub functions raise `NotImplementedError` — no behavior change. CI remains green.

**Exit criterion:** `just build-batch` succeeds; Python `import batch; hasattr(batch, "image")` is True.

---

### ✅ Phase 2 — Image I/O + filesystem (`batch::image`)

**Goal:** Implement `load_image_batch` and `scan_files` in C++, passing all parity tests.

**Tasks:**

1. Implement `load_image_batch_impl` (OpenCV + OpenMP) in `batch/src/image/image_batch.cpp`.
2. Implement `scan_files_impl` (std::filesystem) in `batch/src/image/scan_files.cpp`.
3. Write parity tests in `batch/tests/test_images_cpp.py`:
   - Output shapes match Rust version on same inputs
   - PSNR of thumbnails > 35 dB vs Rust `fast_image_resize` output (INTER_AREA parity)
   - `scan_files` returns identical path sets on a fixture directory
4. Wire dispatch in `base_dispatch.py` (`load_image_batch`, `scan_files`).
5. Benchmark: C++ should reach ≥ 20× vs PIL batch resize on 100-image 4K set.

**Performance target:** 100 × 4K images → thumbnails in < 1.5 s (4 threads) vs ~30 s PIL baseline.

---

### ✅ Phase 3 — Video thumbnails (`batch::video`)

**Goal:** Implement `extract_video_thumbnails_batch` in C++ using OpenCV VideoCapture.

**Tasks:**

1. Implement `extract_video_thumbnails_impl` + `extract_video_thumbnails_batch_impl` (OpenCV + OpenMP).
2. Write parity tests: frame shapes, pixel difference vs Rust ffmpeg-subprocess output ≤ 5 PSNR dB
   (minor decoding differences between FFmpeg CLI and OpenCV's FFmpeg backend are expected).
3. Wire dispatch.
4. Remove `ffmpeg` subprocess dependency from production path.

---

### ✅ Phase 4 — Secure vector DB (`batch::secret`)

**Goal:** Implement all five vault functions in C++.

**Priority order** (most-used first):

1. `hybrid_search_secure` (read path — most latency-sensitive)
2. `insert_listing_secure` (write path)
3. `fetch_all_listings_secure` (bulk read)
4. `delete_listing_secure` (delete)
5. `fetch_listings_as_arrow_pointers` (Arrow FFI export)

**Tasks:**

1. Implement `LockedSecret<N>` and `derive_dek` using libsodium in `batch/src/secret/locked_secret.cpp`.
2. Open SQLCipher connections via `sqlite3_open` + `sqlite3_key`; load sqlite-vec extension.
3. Implement SQL helpers: `upsert_listing`, `cosine_search_vec`, `rrf_fusion`.
4. Implement Arrow C Data Interface export for `fetch_listings_as_arrow_pointers`.
5. Write security unit tests:
   - `derive_dek` is deterministic for same password+salt
   - Wrong password → `SQLITE_NOTADB` on open
   - `LockedSecret` memory is zeroed after destruction (read via `/proc/self/mem` in test)
6. Write parity tests for search results (exact match for small fixture DB).
7. Wire dispatch.

**Security invariants (must hold in C++ as in Rust):**

- Key material never written to heap without `mlock`
- `sodium_memzero` called on all secret buffers before `munlock`
- cv::Mat / STL containers holding key bytes are cleared before deallocation
- No key bytes in stack frames that survive function return (use `LockedSecret` exclusively)

---

### ✅ Phase 5 — HTTP request sequencing (`batch::web`)

**Goal:** Implement `run_web_requests_sequence` in C++ using cpp-httplib.

**Tasks:**

1. Implement `run_web_requests_sequence_impl` with JSON config parsing (nlohmann/json).
2. Implement progress callback through pybind11 with GIL reacquire on each callback invocation.
3. Write parity tests against a local `http.server` fixture (same request sequences, compare JSON output).
4. Wire dispatch.

---

### ✅ Phase 6 — Math library (`batch::math` header-only)

**Goal:** Port `base/src/math/` to C++ header-only library under `batch/include/batch/math/`.

**Tasks:**

1. Port `linalg.rs` → `math/linalg.hpp`: `Matrix<double>` class + PCA (use Eigen3 `SelfAdjointEigenSolver`).
2. Port `graph.rs` → `math/graph.hpp`: `Graph`, BFS, DFS, Kruskal MST/max-MST, SCC, topological sort, `UnionFind`.
3. Port `distance.rs` → `math/distance.hpp`: euclidean, cosine, hamming, bhattacharyya, hellinger.
4. Port `stats.rs` → `math/stats.hpp`: mean, median, std_dev, pearson, z-score.
5. Port `information.rs` → `math/information.hpp`: Shannon entropy, KL/JS divergence, mutual information.
6. Port `dim_reduce.rs` → `math/dim_reduce.hpp`: MDS (double-center + eigen), t-SNE affinity matrix.
7. Replace `UnionFind` duplicated in `bundle_adjust.cpp` with `#include <batch/math/graph.hpp>`.
8. Write Catch2 unit tests in `batch/tests/cpp/test_math.cpp` covering all functions.

---

### ✅ Phase 8 — Core functions: convert, filesystem, finder, merger, wallpaper (COMPLETE)

**Goal:** Port 9 remaining core Python-exposed Rust functions to C++.

**Files created:**
- `base/include/base/core/convert.hpp` / `base/src/core/convert.cpp` — `convert_single_image`, `convert_image_batch` (OpenMP parallel), `convert_video` (ffmpeg subprocess)
- `base/include/base/core/filesystem.hpp` / `base/src/core/filesystem.cpp` — `get_files_by_extension`, `delete_files_by_extensions` (OpenMP parallel), `delete_path`
- `base/include/base/core/finder.hpp` / `base/src/core/finder.cpp` — `find_duplicate_images` (SHA-256, OpenSSL/inline fallback), `find_similar_images_phash` (8×8 pHash + Union-Find)
- `base/include/base/core/merger.hpp` / `base/src/core/merger.cpp` — `merge_images_horizontal`, `merge_images_vertical`, `merge_images_grid` (two-pass OpenCV canvas)
- `base/include/base/core/wallpaper.hpp` / `base/src/core/wallpaper.cpp` — `set_wallpaper_gnome` (gsettings), `evaluate_kde_script` (qdbus via popen)

All registered under `base.core.*`.

---

### ✅ Phase 9 — Web extensions: board crawlers, cloud sync, stubs (COMPLETE)

**Goal:** Port board crawlers and cloud sync from Rust to C++; stub WebDriver-dependent functions.

**Files created:**
- `base/src/web/board_crawler.cpp` — Danbooru (GET), Gelbooru (GET dapi), Sankaku (POST JWT auth + capi-v2), `run_board_crawler(crawler_name, config_json, callback_obj) -> int`
- `base/src/web/cloud_sync.cpp` — Dropbox (list_folder pagination + upload + download), Google Drive (multipart upload), OneDrive (Graph API), `run_sync(provider, config_json, callback_obj) -> str`
- `base/src/web/reverse_image_search.cpp` — STUB (raises RuntimeError; Rust used thirtyfour/Selenium WebDriver, no C++ equivalent)
- `base/src/web/image_crawler.cpp` — STUB (same reason)

All registered into `base.web` by `register_web()`.

---

### ✅ Phase 10 — Utils: legacy migration and slideshow daemon (COMPLETE)

**Goal:** Port `run_legacy_migration` and `run_slideshow_daemon` from Rust to C++.

**Files created:**
- `base/include/base/utils/migration.hpp` / `base/src/utils/migration.cpp` — JSON vault → SQLCipher migration under `#ifdef HAVE_SQLCIPHER`; key derived as `username:password`; raises `RuntimeError` if SQLCipher not compiled
- `base/include/base/utils/slideshow.hpp` / `base/src/utils/slideshow.cpp` — process-lifetime singleton background `std::thread` daemon; actions: start/stop/status/next/configure; config persisted at `~/.image-toolkit/.slideshow_config.json`; uses gsettings for wallpaper advancement

Both registered under `base.utils.*`.

---

### ✅ Phase 11 — Math bindings (COMPLETE)

**Goal:** Expose the Phase 6 math headers (previously header-only, no Python bindings) via pybind11.

**File created:**
- `base/src/math/math_bindings.cpp` — registers `base.math.distance`, `base.math.stats`, `base.math.information`, `base.math.graph`, `base.math.linalg`, `base.math.dim_reduce`

Submodule coverage:
- `distance`: euclidean, euclidean_sq, cosine_similarity, cosine_distance, hamming, bhattacharyya, hellinger, manhattan
- `stats`: mean, median, std_dev, variance, pearson, z_score, min_max_normalize
- `information`: shannon_entropy, kl_divergence, js_divergence, js_distance, mutual_information
- `graph`: Graph class, bfs, dfs, kruskal_mst, kruskal_max_mst, tarjan_scc, topological_sort
- `linalg`: Matrix class, pca (PCAResult with scores/components/explained_variance_ratio)
- `dim_reduce`: mds, tsne_affinities

---

### ✅ Phase 7 — Final rename and Rust retirement (COMPLETE)

**Goal:** Rename `batch/` → `base/` and retire Rust `base/` to archive.

**Prerequisites:** All Phases 1–6 complete and green in CI.

**Tasks:**

1. Rename directory: `mv batch/ base/` (update CMakeLists.txt `project()` name, pybind11 module name
   `PYBIND11_MODULE(base, m)`, and all `import batch` / `_batch` references).
2. Update `just build-batch` → `just build-base` in `tools/build/justfile` and root `justfile`.
3. Update `_HAS_BASE_CPP` shim: `import base as _base_cpp` (no longer needs dual-module logic).
4. Archive Rust codebase: `mv base/ archive/base_rust/` — keep for reference but remove from build.
5. Remove `base` from `Cargo.toml` workspace members and `.github/workflows/` Rust CI jobs.
6. Update `MEMORY.md` and `docs/` to reflect unified `base` C++ module.

### ✅ Phase 12 — Parity verification and integration tests (COMPLETE)

**Goal:** Python integration tests confirming all Phase 8–11 C++ functions behave correctly.
Since the Rust baseline is archived, these are functional correctness tests rather than cross-impl comparisons.

Test files (under `backend/test/base/`):
- `test_parity_core.py`: `base.core` — convert, filesystem, finder, merger, wallpaper
- `test_parity_math.py`: `base.math` — distance, stats, information, graph, linalg, dim_reduce
- `test_parity_utils.py`: `base.utils` + `base.web` — slideshow, migration, web stubs

All tests guarded by `pytest.mark.skipif(not HAS_BASE, reason="base C++ extension not built")`.
Run with: `pytest backend/test/base/ -v -m "not slow"` (when `base` is built).

---

## Data Interface: Python ↔ C++

### numpy ↔ cv::Mat (zero-copy)

Identical pattern as established in the ASP migration (see `include/batch/common.hpp`):

```cpp
cv::Mat mat = batch::mat_from_array(arr);    // zero-copy input
py::array_t<uint8_t> out = batch::array_from_mat(mat);  // owned output
```

Rules carried forward:
- C++ functions never store a `cv::Mat` referencing Python-owned memory across call boundaries.
- All outputs are owned copies (deep copy from `cv::Mat` → `py::array_t`).
- Inputs passed to OpenMP parallel regions must be `cv::Mat::clone()`-d inside the thread.

### std::string ↔ Python str

All path strings use UTF-8 `std::string`. pybind11 converts Python `str` ↔ `std::string` automatically
(using UTF-8 encoding on all platforms, matching Python's default filesystem encoding on Linux).

### GIL management

All parallel (OpenMP) loops use `py::gil_scoped_release` before the parallel block and
`py::gil_scoped_acquire` for any Python callbacks inside:

```cpp
{
    py::gil_scoped_release release;
    #pragma omp parallel for schedule(dynamic)
    for (int i = 0; i < N; i++) { /* pure C++ work */ }
}  // GIL reacquired here
```

---

## Compatibility / Fallback Strategy

### Dispatch shim (`backend/src/utils/base_dispatch.py`)

```python
_HAS_BASE_CPP = False
try:
    import batch as _batch_cpp
    _HAS_BASE_CPP = getattr(_batch_cpp, "image", None) is not None
except ImportError:
    pass

if not _HAS_BASE_CPP:
    import base as _base_rust


def load_image_batch(paths, thumb_w=256, thumb_h=256, keep_aspect=True):
    if _HAS_BASE_CPP:
        return _batch_cpp.image.load_image_batch(paths, thumb_w, thumb_h, keep_aspect)
    return _base_rust.load_image_batch(paths, thumb_w, thumb_h, keep_aspect)


def scan_files(root_dir, extensions, recursive=True):
    if _HAS_BASE_CPP:
        return _batch_cpp.image.scan_files(root_dir, extensions, recursive)
    return _base_rust.scan_files(root_dir, extensions, recursive)

# … one wrapper per function …
```

### Guarantees

- All call sites pass without `batch` built (Rust fallback active).
- CI default: Rust module (unchanged from current).
- CI optional job: builds C++ `batch`, runs `batch/tests/` parity suite.
- Parity tolerances: image thumbnails PSNR > 35 dB; search results exact match; path sets identical.

---

## Build System

### CMakeLists.txt additions (Phase 1)

```cmake
# New source groups
target_sources(batch PRIVATE
    src/image/image_batch.cpp
    src/image/scan_files.cpp
    src/video/video_batch.cpp
    src/secret/vault_db.cpp
    src/secret/locked_secret.cpp
    src/web/web_requests.cpp
)

# libsodium (Phase 4)
find_package(PkgConfig REQUIRED)
pkg_check_modules(SODIUM REQUIRED libsodium)
target_include_directories(batch PRIVATE ${SODIUM_INCLUDE_DIRS})
target_link_libraries(batch PRIVATE ${SODIUM_LIBRARIES})

# cpp-httplib (Phase 5, header-only)
FetchContent_Declare(cpp-httplib
    GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
    GIT_TAG        v0.16.0)
FetchContent_MakeAvailable(cpp-httplib)
target_link_libraries(batch PRIVATE httplib::httplib)

# nlohmann/json (Phase 5, header-only, already available via FetchContent pattern)
FetchContent_Declare(json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG        v3.11.3)
FetchContent_MakeAvailable(json)
target_link_libraries(batch PRIVATE nlohmann_json::nlohmann_json)
```

### `just` recipe additions (Phase 1)

```makefile
# tools/build/justfile — no change needed; just build-batch already handles all batch/ sources
```

The `just build-batch` recipe already runs CMake with the batch/ directory — adding new source files
to CMakeLists.txt is all that is needed.

---

## Testing Strategy

### Parity tests (`batch/tests/test_*_cpp.py`)

One file per phase:

| Phase | File | Key assertions |
|---|---|---|
| 2 | `test_images_cpp.py` | Thumbnail shapes, PSNR > 35 dB vs Rust, scan_files set equality |
| 3 | `test_video_cpp.py` | Frame shapes, PSNR > 30 dB vs ffmpeg-subprocess reference |
| 4 | `test_secret_cpp.py` | DEK determinism, wrong-password error, search result exact match |
| 5 | `test_web_cpp.py` | JSON output equality vs local http.server fixture |
| 6 | `test_math_catch2.cpp` | Catch2 unit tests for all math functions |

All Python parity tests follow the ASP pattern:

```python
import pytest
try:
    import batch
    HAS_BATCH = hasattr(batch, "image")
except ImportError:
    HAS_BATCH = False

pytestmark = pytest.mark.skipif(not HAS_BATCH, reason="batch not built")
```

### Security tests (Phase 4)

```python
# batch/tests/test_vault_security.py
import ctypes, gc

def test_locked_secret_zeroed_after_drop():
    """Confirm DEK memory is zeroed after the vault function returns."""
    # Exercise vault function; then check that no key bytes remain in process heap.
    # Implementation: mark memory region before call, verify zeroed after call.
    pass  # Implementation left to Phase 4 detail
```

---

## Performance Targets

| Function | Rust baseline | C++ target | Speedup estimate | Phase |
|---|---|---|---|---|
| `load_image_batch` (100 × 4K, 4 threads) | ~8 s | < 1.5 s | 5× | 2 |
| `scan_files` (100k file tree) | ~0.3 s | ~0.1 s | 3× | 2 |
| `extract_video_thumbnails_batch` (10 × 30s video) | ~12 s (subprocess) | ~4 s (VideoCapture) | 3× | 3 |
| `hybrid_search_secure` (1k embeddings, k=10) | ~25 ms | ~20 ms | ~1.2× | 4 |
| `fetch_listings_as_arrow_pointers` (10k rows) | ~50 ms | ~40 ms | ~1.2× | 4 |
| `run_web_requests_sequence` (10 requests) | network-bound | network-bound | 1× | 5 |

Note: The vault and HTTP functions are I/O-bound, so C++ speedup is minimal. The primary benefit there
is build unification and removal of the Rust ABI dependency.

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `mlock` quota exhausted on developer machine (RLIMIT_MEMLOCK) | Medium | Medium | `LockedSecret` logs warning and continues without mlock (same behavior as Rust `MemoryLockedKey`) |
| libsodium not installed on developer machine | Medium | High | Add `pkg_check_modules(SODIUM REQUIRED libsodium)` with clear error; document `apt install libsodium-dev` |
| sqlite-vec C extension API changes | Low | Medium | Pin version in CMakeLists FetchContent |
| Arrow C Data Interface memory lifecycle (who frees `ArrowArray`) | High | High | Follow AIA spec: producer sets `.release` callback; consumer calls it. Wrap in `std::unique_ptr` with custom deleter |
| OpenCV VideoCapture FFmpeg backend decoding differences from ffmpeg CLI | Medium | Low | Allow PSNR tolerance ≥ 30 dB in tests; document expected variance |
| GIL deadlock in vault callback path | Low | High | Vault functions use no Python callbacks; GIL released for entire DB operation |
| Security regression: key bytes leaking via exception unwind | Medium | High | Use RAII `LockedSecret` exclusively; no raw key arrays on stack |
| pybind11 ABI break on Python upgrade (3.11 → 3.12) | Low | Medium | Rebuild `batch` for each Python minor version; CI pins 3.11 |
| Phase 7 rename breaks downstream importers | Low | High | Add `import base` → `import batch` compatibility shim for one release cycle |

---

## Appendix: Key File References

| Role | File |
|---|---|
| Rust module entry point | `base/src/lib.rs` |
| Rust image converter | `base/src/core/image_converter.rs` |
| Rust secure vector DB | `base/src/core/secure_vector_db.rs` |
| Rust HTTP client | `base/src/web/clients/web_requests.rs` |
| Rust math library | `base/src/math/mod.rs` |
| Rust crawler base | `base/src/web/crawlers/crawler.rs` |
| C++ batch CMakeLists | `batch/CMakeLists.txt` |
| C++ zero-copy converters | `batch/include/batch/common.hpp` |
| C++ ASP submodule reference | `archive/moon/asp_cpp_migration.md` |
| Dispatch shim (to be created) | `backend/src/utils/base_dispatch.py` |

---

## Document History

*Created: 2026-06-29. Status: OPEN — Phase 1 not yet started.*
