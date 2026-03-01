# RAM Reduction Roadmap

Comprehensive audit of memory usage across Image Toolkit.
Last updated: 2026-03-01. Completed items are marked ✅.

---

## Already Completed

### ✅ Gallery base-class thumbnail caches converted to bounded LRU

**Files changed**

- `gui/src/utils/lru_image_cache.py` _(created)_
- `gui/src/classes/abstract_class_two_galleries.py`
- `gui/src/classes/abstract_class_single_gallery.py`

**What was done**

`_found_pixmap_cache`, `_selected_pixmap_cache`, and `_initial_pixmap_cache` were
unbounded `dict[str, QPixmap]` objects in both gallery base classes.
On X11/Linux a `QPixmap` carries both a client-side pixel buffer **and** a
server-side backing pixmap, roughly doubling the per-entry cost compared to `QImage`.

All three caches were replaced with `LRUImageCache` (an `OrderedDict`-backed LRU
with configurable `maxsize`). Signal handlers now store `QImage`; retrieval sites
convert to `QPixmap` only at the moment a widget needs it.

| Cache                                    | Cap         | Approx. RAM ceiling |
| ---------------------------------------- | ----------- | ------------------- |
| `_found_pixmap_cache`                    | 300 entries | ~38 MB              |
| `_selected_pixmap_cache`                 | 200 entries | ~25 MB              |
| `_initial_pixmap_cache` (single gallery) | 300 entries | ~38 MB              |

**Before / after (10 000-image session)**

| Scenario                         | Before   | After  |
| -------------------------------- | -------- | ------ |
| All pages viewed (found gallery) | ~2.46 GB | ~38 MB |
| 1 000-image directory            | ~246 MB  | ~38 MB |

**Side-effects / trade-offs**
When paging back more than ~3 pages, thumbnails that have been evicted from the
LRU are re-loaded from disk (≈50–200 ms delay). Thumbnails on the current and
adjacent pages are always served from cache.

### ✅ QPixmap threading violation fixed in ImageLoaderWorker

`gui/src/helpers/image/image_loader_worker.py` — the `except` block emitted
`QPixmap()` from a `QRunnable` worker thread. `QPixmap` is not thread-safe
(main-thread only). Changed to emit `QImage()` instead.

---

## ✅ Tier 1 — High impact, low effort (completed 2026-03-01)

---

### ✅ 1 · Three tabs override the parent LRU cache with unbounded QPixmap dicts

The `AbstractClassSingleGallery` base class now provides a bounded
`LRUImageCache`. Three concrete tabs re-declare `_initial_pixmap_cache` in
their own `__init__` (or on scan-start), silently shadowing the parent's bounded
cache with an unbounded `dict[str, QPixmap]`.

| Tab               | File                                       | Line | Declaration                           |
| ----------------- | ------------------------------------------ | ---- | ------------------------------------- |
| WallpaperTab      | `gui/src/tabs/core/wallpaper_tab.py`       | 168  | `Dict[str, QPixmap] = {}` constructor |
| ImageExtractorTab | `gui/src/tabs/core/image_extractor_tab.py` | 69   | `Dict[str, QPixmap] = {}` constructor |
| ReverseSearchTab  | `gui/src/tabs/web/reverse_search_tab.py`   | 213  | `= {}` reset on each new scan         |

**WallpaperTab is the most impactful.** It has 17 read/write sites that all
touch this dict and stores full `QPixmap` objects (not `QImage`). A wallpaper
library of 1 000 images leaves ≈250 MB permanently allocated.

**Fix (each tab)**

1. Delete the local `_initial_pixmap_cache` declaration entirely.
   The parent's `LRUImageCache(maxsize=300)` is inherited automatically.

2. Any write that currently stores a `QPixmap`:

   ```python
   # before
   self._initial_pixmap_cache[path] = thumb          # thumb is QPixmap

   # after
   self._initial_pixmap_cache[path] = thumb.toImage() # store QImage
   ```

3. Any read that passes the value directly to a widget:

   ```python
   # before
   thumb = self._initial_pixmap_cache.get(path)
   label.setPixmap(thumb)

   # after
   _cached = self._initial_pixmap_cache.get(path)
   thumb = QPixmap.fromImage(_cached) if isinstance(_cached, QImage) else _cached
   label.setPixmap(thumb)
   ```

**ImageExtractorTab extra note**
`image_extractor_tab.py:1513` stores a `QPixmap` returned by
`_generate_video_thumbnail()` before calling `start_loading_gallery`. Convert
to `QImage` at that call site. The dict is also passed as `pixmap_cache=` to
`start_loading_gallery`, which now iterates items — so the inherited base-class
behaviour already handles populating the LRU from it correctly.

**Estimated saving: 100–500 MB** depending on library size.

---

### ✅ 2 · DuplicateScanWorker.scan_cache holds all image descriptors simultaneously

`gui/src/helpers/core/duplicate_scan_worker.py:37`

```python
self.scan_cache = {}   # populated by _on_task_result(), one entry per image
```

Every descriptor computed by the worker tasks is accumulated in `scan_cache`
before the sequential comparison phase can begin. The entry size depends on
the chosen method:

| Method      | Per-image size                 | 10 000 images |
| ----------- | ------------------------------ | ------------- |
| `"phash"`   | 8 bytes (int64)                | < 1 MB ✓      |
| `"orb"`     | ~2–5 KB                        | ~20–50 MB     |
| `"siamese"` | 512 × float32 = 2 KB           | ~20 MB        |
| `"sift"`    | ~10–50 KB (variable keypoints) | ~100–500 MB   |
| `"ssim"`    | grayscale crop ~50–200 KB      | ~500 MB–2 GB  |

**Fix implemented (SIFT and SSIM only)**

Added `_chunked_compare(method_prefix, is_similar_fn, chunk_size=500)` to
`DuplicateScanWorker`. Sorts `scan_cache` keys, splits into chunks of 500, and
compares all chunk pairs using a union-find structure for transitive grouping.
After chunk A is compared against all later chunks, its entries are `del`-ed from
`scan_cache`, capping live descriptors to at most 2 × 500 at any time.

For `"phash"`, `"orb"`, and `"siamese"` the cache is already small — no change
needed.

**Estimated saving: 100–500 MB** for SIFT/SSIM on large directories.

---

## ✅ Tier 2 — Medium impact, medium effort

---

### ✅ 3 · \_loaded_results_buffer accumulates QPixmaps before render

`gui/src/tabs/database/scan_metadata_tab.py:83`

```python
self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
```

Worker signals append `(path, QPixmap)` tuples at line 1120. The buffer is
flushed to the UI and cleared at line 560. If the loader emits results faster
than the UI renders them, the buffer is a holding area for unbounded `QPixmap`
objects.

**Fix**

Change the buffer to store `QImage` instead of `QPixmap`:

```python
self._loaded_results_buffer: List[Tuple[str, QImage]] = []
```

At the append site (line 1120), store `pixmap.toImage()` if the worker emits
`QPixmap`, or store the `QImage` directly if you change the worker signal type.
At the flush/render site, call `QPixmap.fromImage(img)` before passing to the
widget.

This halves peak buffer RAM. If further reduction is needed, add a
`maxlen=500` deque and pause the worker when the deque is full.

**Estimated saving: 50–250 MB peak** during heavy database scans.

---

### ✅ 4 · Tag checkbox dicts scale linearly with database tag count

`gui/src/tabs/database/scan_metadata_tab.py:246`
`gui/src/tabs/database/search_tab.py:140`

```python
self.tag_checkboxes = {}   # one live QCheckBox per tag
```

Both tabs call `_setup_tag_checkboxes()` which queries all tags from the
database and creates one `QCheckBox` widget per tag. The dict is replaced
wholesale on every refresh. At small tag counts (< 500) this is negligible.
At 5 000+ tags it materialises thousands of Qt widget objects simultaneously
(≈5–20 MB of Qt heap, plus GC pressure on each rebuild).

**Fix**

Replace the flat checkbox grid with a `QListWidget` in checkable-item mode:

```python
list_widget = QListWidget()
for tag in tags:
    item = QListWidgetItem(tag)
    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
    item.setCheckState(Qt.Unchecked)
    list_widget.addItem(item)
```

`QListWidget` uses a virtual item model and only renders the visible rows.
Reading checked state:

```python
checked = [
    list_widget.item(i).text()
    for i in range(list_widget.count())
    if list_widget.item(i).checkState() == Qt.Checked
]
```

This replaces N live `QCheckBox` widgets with N lightweight `QListWidgetItem`
value objects.

**Estimated saving: 5–20 MB** per tab instance; eliminates GC spikes on tag
refresh.

---

### ✅ 5 · source_path_to_widget map in ImageExtractorTab never shrinks

`gui/src/tabs/core/image_extractor_tab.py:72`

```python
self.source_path_to_widget: Dict[str, QWidget] = {}
```

This map holds a strong reference to each card widget for every processed
video. Qt's `deleteLater()` cannot actually free the C++ object while a
Python strong reference to the wrapper exists. The result is that card widgets
for off-screen pages accumulate silently.

**Fix**

Pop entries from `source_path_to_widget` in the same loop that removes widgets
from the layout during page changes (mirror the pattern in
`AbstractClassTwoGalleries.refresh_found_gallery`).

---

### ✅ 6 · ML model weights stay resident after the feature is used

**SiameseModelLoader** (`backend/src/models/siamese_network.py:14`)
Class-level singleton: `_model = None`. On first call to `get_embedding()`,
ResNet-18 is loaded (~45 MB) and never freed.

**GANWrapper** (`backend/src/models/gan_wrapper.py:34`)
`self.netG` is loaded in `__init__` via `torch.hub.load()` and persists for the
lifetime of the wrapper instance.

**GAN (training)** (`backend/src/models/gan.py:27–28`)
`netG` + `netD` + two Adam optimizer state dicts — typically 50–200 MB.

**Fix**

For the inference-only paths (Siamese, GANWrapper), add an `unload()` method:

```python
def unload(self):
    self._model = None
    self._instance = None    # reset singleton (SiameseModelLoader)
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
```

Call `unload()` from the worker's `finished` signal when the duplicate-scan
completes. The model reloads on next use (one-time ~2 s delay).

For training runs (GAN), no change is needed — keeping weights in RAM during
an active training session is expected.

**Estimated saving: 45–200 MB** while the feature is not actively in use.

---

## ✅ Tier 3 — Small impact, structural hygiene

---

### ✅ 7 · Signal lambda closures capture strong widget references

`gui/src/classes/abstract_class_two_galleries.py:484`

```python
worker.signals.result.connect(
    lambda p, px: self._on_selected_image_loaded(p, px, target_widget)
)
```

The lambda captures `target_widget` (a `QWidget`) by strong reference. If the
worker finishes after the user pages away and the widget has been removed from
the layout, `deleteLater()` cannot release the C++ object while this closure
keeps the Python wrapper alive.

**Fix**

Use a weak reference:

```python
import weakref
weak = weakref.ref(target_widget)
worker.signals.result.connect(
    lambda p, px, w=weak: self._on_selected_image_loaded(p, px, w())
    if w() is not None else None
)
```

Or, preferably, look the widget up from `selected_card_map` by path inside the
handler instead of capturing it directly.

---

### ✅ 8 · PostgreSQL queries materialise full result sets

`backend/src/database/image_database.py`

`cursor.fetchall()` loads entire result sets into Python lists. For queries
bounded by a small `LIMIT` (e.g. nearest-neighbour search returning 10 rows)
this is fine. For bulk export queries or queries that could return thousands
of rows (e.g. tag searches against large collections), each 512-dim float32
embedding vector costs 2 KB; 10 000 rows × 2 KB = ~20 MB materialised at once.

**Fix**

Use `cursor.fetchmany(batch_size)` or a named server-side cursor for any query
without a small fixed `LIMIT`:

```python
cursor.name = "bulk_export_cursor"   # enables server-side cursor in psycopg2
cursor.execute("SELECT ...")
while True:
    batch = cursor.fetchmany(200)
    if not batch:
        break
    process(batch)
```

---

### ✅ 9 · open_queue_windows and open_image_preview_windows are list-bounded

`gui/src/tabs/core/wallpaper_tab.py:176–177`

```python
self.open_queue_windows: List[QWidget] = []
self.open_image_preview_windows: List[QWidget] = []
```

The lists are properly cleaned in the `closeEvent` (lines 761–769) and via
callbacks when windows close (lines 885–912). However, if a user repeatedly
opens and closes preview windows without the callbacks firing (e.g. a C++
`RuntimeError` on a deleted widget), stale entries accumulate.

**Fix**

Wrap the cleanup callback with a guard that also sweeps the list for dead
references:

```python
self.open_queue_windows = [w for w in self.open_queue_windows
                            if not sip.isdeleted(w)]
```

(Requires `from PyQt6 import sip` or the equivalent PySide6 `shiboken6`.)

---

## Tier 4 — Backend (`backend/`) memory opportunities

---

### 1 · ML model singletons never explicitly unload (PyTorch) (✅ done)

**Files**: `backend/src/models/siamese_network.py`, `backend/src/models/gan_wrapper.py`, `backend/src/models/sd3_wrapper.py`

All three wrappers provide `unload()` methods, but the GUI/caller code never
invokes them after operations complete. Models remain in RAM indefinitely:

| Model               | RAM usage (idle)             | Method                                         |
| ------------------- | ---------------------------- | ---------------------------------------------- |
| ResNet-18 (Siamese) | ~45 MB (CPU) / ~90 MB (CUDA) | `SiameseModelLoader().unload()`                |
| AnimeGAN2           | ~50–100 MB                   | `GanWrapper.unload()`                          |
| Stable Diffusion 3  | 2–8 GB                       | Manual `del pipe` + `torch.cuda.empty_cache()` |

**Current behavior**: `SiameseModelLoader` is a singleton that calls
`load_model()` on first use and holds the model in `_model` forever. The GUI
duplicate scanner uses Siamese mode, then switches to SIFT — the ResNet-18
remains loaded.

**Fix**

1. In GUI duplicate scanner (`gui/src/helpers/core/duplicate_scan_worker.py`),
   call `SiameseModelLoader().unload()` at the end of the Siamese comparison
   branch (after line 141 in current code, before emitting `finished`).

2. In GAN tab (`gui/src/tabs/ml/gan_tab.py`), call `self.gan_wrapper.unload()`
   when generation completes or tab is closed.

3. For SD3, the wrapper is currently a static method with no persistent state.
   Convert to a class instance so the pipeline can be cached and unloaded:

   ```python
   class SD3Wrapper:
       def __init__(self):
           self.pipe = None

       def load_model(self, model_path):
           if self.pipe is None:
               self.pipe = StableDiffusion3Pipeline.from_pretrained(...)

       def unload(self):
           if self.pipe is not None:
               del self.pipe
               self.pipe = None
           torch.cuda.empty_cache()
   ```

**Estimated saving**: 45–200 MB (Siamese + GAN), 2–8 GB (SD3 if used).

---

### 2 · Database `fetchall()` materializes unbounded result sets (✅ done)

**Files**: `backend/src/database/image_database.py:445,451,457,463,469`

Five methods call `cur.fetchall()` without limits:

- `get_all_tags()` — line 445
- `get_all_groups()` — line 451
- `get_all_subgroups()` — line 457
- `get_subgroups_for_group()` — line 463
- `get_all_subgroups_detailed()` — line 469

For 5 000 tags, `fetchall()` creates a Python list with 5 000 tuples in memory
at once (~50–100 KB). For 10 000 tags with metadata, this can be ~1 MB.

The `search_similar_images` method (lines 410–439) already uses a server-side
cursor with `fetchmany(100)` batching — this is correct and efficient.

**Fix**

These methods are typically called for UI population (tag dropdowns, group
lists). Since the GUI needs the full list anyway (for checkboxes/comboboxes),
`fetchall()` is acceptable here **if** the result count is known to be bounded
(< 10 000 items).

However, for future-proofing:

- Add an optional `limit` parameter to each method
- Document the expected max result size in docstrings

**Estimated saving**: Minimal (< 5 MB) for typical usage. Good practice for
future growth.

---

### 3 · N+1 query in `search_similar_images` (line 433) (✅ done)

**Files**: `backend/src/database/image_database.py:433`

Inside the fetch loop, `get_image_tags(image_id)` is called for each row:

```python
for row in rows:
    image_id = row["id"]
    image_data = dict(row)
    image_data.pop("embedding", None)
    # Caution: calling get_image_tags inside a fetch loop can be N+1 slow,
    # but we are just fixing the fetchall RAM spike for now.
    image_data["tags"] = self.get_image_tags(image_id)
    results.append(image_data)
```

For 100 search results, this issues 100 separate `SELECT` queries (1 + 100 =
N+1 problem). This is a **latency** issue, not a RAM issue, but materializing
100 tag lists in memory simultaneously adds ~10–50 KB depending on tag counts.

**Fix**

Collect all `image_id` values from the batch, then fetch tags for all IDs in a
single query using `WHERE image_id = ANY(%s)`:

```python
image_ids = [row["id"] for row in rows]
# Bulk fetch all tags for this batch
cur.execute(_tags["get_tags_for_images_bulk"], (image_ids,))
tags_by_id = {}
for tag_row in cur.fetchall():
    tags_by_id.setdefault(tag_row["image_id"], []).append(tag_row["tag_name"])

for row in rows:
    image_id = row["id"]
    image_data = dict(row)
    image_data.pop("embedding", None)
    image_data["tags"] = tags_by_id.get(image_id, [])
    results.append(image_data)
```

Requires adding a new SQL query `get_tags_for_images_bulk` in `tags.sql`.

**Estimated saving**: ~50 KB per 100-result batch (tag list overhead reduction).
More importantly, reduces query latency by ~10–100×.

---

### 4 · Diffusion pipeline keeps all components in VRAM (✅ done)

**Files**: `backend/src/models/sd3_wrapper.py:45`

The code uses `pipe.enable_model_cpu_offload()`, which is good for VRAM
management (moves components to CPU RAM when not in use). However, CPU RAM
usage is still high (~4–6 GB for SD3 Medium).

For desktop environments with limited RAM (< 16 GB), consider:

- `enable_sequential_cpu_offload()` — more aggressive offloading (slower, but
  uses ~2 GB less)
- `low_cpu_mem_usage=True` when loading the model

**Current behavior**:

```python
pipe.enable_model_cpu_offload()  # ~4–6 GB CPU RAM
```

**Potential improvement**:

```python
pipe.enable_sequential_cpu_offload()  # ~2–4 GB CPU RAM (slower inference)
```

**Estimated saving**: 1–3 GB for SD3 operations (at the cost of ~20% slower
generation).

---

### 5 · GAN training accumulates all images in `SimpleFolderDataset` (✅ done)

**Files**: `backend/src/models/gan_wrapper.py:89–107`

The `SimpleFolderDataset` walks the entire directory and stores all image paths
in `self.image_paths` list at init time:

```python
for root, _, files in os.walk(root_dir):
    for file in files:
        if file.lower().endswith((...)):
            self.image_paths.append(os.path.join(root, file))
```

For 10 000 training images, the list of paths consumes ~1–2 MB (negligible).
However, PyTorch's `DataLoader` with `num_workers=0` means all preprocessing
happens in the main process, and the `__getitem__` method loads the full image
into RAM:

```python
img = Image.open(self.image_paths[idx]).convert("RGB")
return self.transform(img)  # 512×512 RGB = ~768 KB per image
```

With `batch_size=1`, only one image is loaded at a time, so peak RAM is minimal
(~1–2 MB per batch). **No fix needed** for current single-batch training.

If batch size increases (e.g. `batch_size=8`), consider setting `num_workers=2`
to use background processes for loading, capping RAM to ~2 × batch_size images.

**Estimated saving**: Already optimal for single-image batches.

---

## Tier 5 — Rust (`base/`) memory opportunities

---

### 1 · Image merge operations load all images into memory at once

**Files**: `base/src/core/image_merger.rs`

The horizontal, vertical, and grid merge functions all collect all input images
into a single `Vec<DynamicImage>` before processing:

```rust
let images: Vec<DynamicImage> = image_paths
    .iter()
    .filter_map(|p| load_img(p).ok())
    .collect();  // ← All images loaded at once
```

For merging 100 large images (4K resolution), this can temporarily consume
~2–4 GB of RAM.

**Potential fix**

Stream images one at a time for operations that don't require all images
simultaneously:

- For horizontal/vertical merges: compute canvas dimensions in a first pass
  (cheap metadata read), allocate canvas, then stream each image, paste, and
  drop.
- For grid merges: same approach — pre-compute cell sizes, then stream.

**Estimated saving**: 1–3 GB peak during large merge operations.

---

### 2 · Batch image conversion uses rayon but all outputs are collected

**Files**: `base/src/core/image_converter.rs:148–165`

The `convert_image_batch_core` function processes images in parallel using
rayon's `par_iter()`, which is excellent for throughput, but the results are
collected into a single `Vec<String>`:

```rust
image_pairs
    .par_iter()
    .filter_map(|(path, out_path)| { ... })
    .collect()  // ← Blocks until all conversions complete
```

For a batch of 1 000 images, peak RAM is ~N worker threads × image size (e.g. 8
threads × 20 MB = 160 MB). The collection itself is lightweight (just paths),
so this is already fairly optimal.

**No fix needed** — current design is efficient for batch conversion. The
parallel processing with rayon already uses thread-local buffering and doesn't
load all images into a single allocation.

---

### 3 · WebDriver instances in crawlers may leak memory if not explicitly closed

**Files**: `base/src/web/crawler.rs`, `base/src/web/image_crawler.rs`

Selenium WebDriver instances allocate browser processes and IPC buffers. The
`quit()` method properly closes the driver, but if Python code raises an
exception before calling `quit()`, the driver process may be orphaned.

**Potential fix**

In the PyO3 bindings, wrap the WebDriver in a RAII guard that calls `quit()`
on drop, or use `scopeguard` to ensure cleanup on unwind:

```rust
use scopeguard::defer;
let driver = WebDriver::new(...).await?;
defer! { let _ = driver.quit().await; }
```

**Estimated saving**: Prevents memory leaks in the browser subprocess (hundreds
of MB per orphaned instance).

---

### 4 · Image board crawlers accumulate all posts before filtering

**Files**: `base/src/web/image_board_crawler.rs`

The crawler fetches posts page-by-page and likely accumulates metadata in
memory. For large result sets (e.g. 1 000 pages × 100 posts/page = 100 000
entries), JSON metadata can grow to ~50–100 MB.

**Potential fix**

Stream processing: download and filter each page immediately, only keeping the
final download URLs, then release the JSON metadata after each page.

**Estimated saving**: 50–100 MB for large multi-page crawls.

---

### 5 · `DynamicImage` clones in resize and transform operations

**Files**: `base/src/core/image_converter.rs:137`, `image_merger.rs:23`

Several functions call `.clone()` on `DynamicImage`:

- `apply_ar_transform` clones when no transform is needed (line 137)
- `fast_resize` clones when dimensions match (line 23 in merger)

`DynamicImage::clone()` creates a full copy of the pixel buffer (e.g. 4K RGBA =
~32 MB per clone).

**Potential fix**

Use move semantics or `Cow<DynamicImage>` to avoid cloning when no transformation
is needed:

```rust
fn apply_ar_transform(img: DynamicImage, ratio: Option<f32>, mode: &str) -> Result<DynamicImage> {
    if let Some(r) = ratio {
        match mode {
            "pad" => pad_image(&img, r),
            "stretch" => stretch_image(&img, r),
            _ => crop_center(&img, r),
        }
    } else {
        Ok(img)  // No clone, just return ownership
    }
}
```

Change the function signature to take ownership (`img: DynamicImage` instead of
`img: &DynamicImage`) at call sites that can afford the move.

**Estimated saving**: ~30–60 MB per operation that currently clones unnecessarily.

---

## Memory budget summary

| Source                                                               | Worst-case before | After all fixes                     |
| -------------------------------------------------------------------- | ----------------- | ----------------------------------- |
| Gallery base-class caches (✅ done)                                  | Unbounded QPixmap | ~100 MB (3 × LRU cap)               |
| WallpaperTab / ImageExtractorTab / ReverseSearchTab caches (✅ done) | Unbounded QPixmap | ~75 MB (inherited LRU)              |
| DuplicateScanWorker.scan_cache (SIFT, 10 k images) (✅ done)         | ~100–500 MB       | ~10 MB per chunk                    |
| \_loaded_results_buffer peak                                         | Unbounded QPixmap | ~5 MB (QImage + optional deque cap) |
| tag_checkboxes (5 000 tags × 2 tabs)                                 | ~10–40 MB         | < 1 MB (QListWidget virtual)        |
| Siamese ResNet-18 + GAN weights (idle, backend)                      | 45–200 MB         | 0 MB (unload on finish)             |
| source_path_to_widget widget leak                                    | Grows per session | Eliminated                          |
| **GUI subtotal (active 10 k-image session)**                         | **800 MB – 3 GB** | **~200–300 MB**                     |
| ML models not unloaded (Siamese + GAN, backend)                      | 45–200 MB         | 0 MB (explicit unload)              |
| Stable Diffusion 3 CPU RAM (backend)                                 | 4–6 GB            | 2–4 GB (sequential offload)         |
| Database fetchall() (backend)                                        | ~1–5 MB           | ~1 MB (limit params)                |
| N+1 tag queries (backend)                                            | ~50 KB/batch      | ~5 KB/batch (bulk fetch)            |
| **Backend subtotal (active ML session)**                             | **4–6 GB**        | **2–4 GB**                          |
| Image merge (100 × 4K images, Rust)                                  | ~2–4 GB peak      | ~200 MB peak (streaming)            |
| DynamicImage clones (per operation, Rust)                            | ~30–60 MB         | 0 MB (move semantics)               |
| Image board crawler metadata (1 000 pages, Rust)                     | ~50–100 MB        | ~5 MB (stream processing)           |
| Orphaned WebDriver instances (Rust)                                  | Hundreds of MB    | 0 MB (RAII cleanup)                 |
| **Rust subtotal (large batch operations)**                           | **2–5 GB**        | **~200–300 MB**                     |
| **Combined total (worst-case: GUI + ML + batch ops)**                | **7–14 GB**       | **~600 MB – 1.2 GB**                |

---

## Verification checklist

After implementing each tier:

1. Launch the app and log in.
2. Open Convert tab → browse a directory with 500+ images → page through 5+ pages
   forward and back. Observe Python RSS in `htop`.
3. Open Wallpaper tab → add 500+ images to the queue. Observe RSS.
4. Run duplicate scan with SIFT on a 1 000-image directory. Observe peak RSS.
5. Run `pytest` — no regressions expected.
