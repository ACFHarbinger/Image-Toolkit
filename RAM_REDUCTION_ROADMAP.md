# RAM Reduction Roadmap

Comprehensive audit of memory usage across Image Toolkit.
Last updated: 2026-03-01. Completed items are marked ✅.

---

## Already Completed

### ✅ Gallery base-class thumbnail caches converted to bounded LRU

**Files changed**
- `gui/src/utils/lru_image_cache.py` *(created)*
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

| Cache | Cap | Approx. RAM ceiling |
|---|---|---|
| `_found_pixmap_cache` | 300 entries | ~38 MB |
| `_selected_pixmap_cache` | 200 entries | ~25 MB |
| `_initial_pixmap_cache` (single gallery) | 300 entries | ~38 MB |

**Before / after (10 000-image session)**

| Scenario | Before | After |
|---|---|---|
| All pages viewed (found gallery) | ~2.46 GB | ~38 MB |
| 1 000-image directory | ~246 MB | ~38 MB |

**Side-effects / trade-offs**
When paging back more than ~3 pages, thumbnails that have been evicted from the
LRU are re-loaded from disk (≈50–200 ms delay). Thumbnails on the current and
adjacent pages are always served from cache.

### ✅ QPixmap threading violation fixed in ImageLoaderWorker

`gui/src/helpers/image/image_loader_worker.py` — the `except` block emitted
`QPixmap()` from a `QRunnable` worker thread.  `QPixmap` is not thread-safe
(main-thread only).  Changed to emit `QImage()` instead.

---

## ✅ Tier 1 — High impact, low effort (completed 2026-03-01)

---

### ✅ 1 · Three tabs override the parent LRU cache with unbounded QPixmap dicts

The `AbstractClassSingleGallery` base class now provides a bounded
`LRUImageCache`.  Three concrete tabs re-declare `_initial_pixmap_cache` in
their own `__init__` (or on scan-start), silently shadowing the parent's bounded
cache with an unbounded `dict[str, QPixmap]`.

| Tab | File | Line | Declaration |
|---|---|---|---|
| WallpaperTab | `gui/src/tabs/core/wallpaper_tab.py` | 168 | `Dict[str, QPixmap] = {}` constructor |
| ImageExtractorTab | `gui/src/tabs/core/image_extractor_tab.py` | 69 | `Dict[str, QPixmap] = {}` constructor |
| ReverseSearchTab | `gui/src/tabs/web/reverse_search_tab.py` | 213 | `= {}` reset on each new scan |

**WallpaperTab is the most impactful.**  It has 17 read/write sites that all
touch this dict and stores full `QPixmap` objects (not `QImage`).  A wallpaper
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
`_generate_video_thumbnail()` before calling `start_loading_gallery`.  Convert
to `QImage` at that call site.  The dict is also passed as `pixmap_cache=` to
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
before the sequential comparison phase can begin.  The entry size depends on
the chosen method:

| Method | Per-image size | 10 000 images |
|---|---|---|
| `"phash"` | 8 bytes (int64) | < 1 MB ✓ |
| `"orb"` | ~2–5 KB | ~20–50 MB |
| `"siamese"` | 512 × float32 = 2 KB | ~20 MB |
| `"sift"` | ~10–50 KB (variable keypoints) | ~100–500 MB |
| `"ssim"` | grayscale crop ~50–200 KB | ~500 MB–2 GB |

**Fix implemented (SIFT and SSIM only)**

Added `_chunked_compare(method_prefix, is_similar_fn, chunk_size=500)` to
`DuplicateScanWorker`.  Sorts `scan_cache` keys, splits into chunks of 500, and
compares all chunk pairs using a union-find structure for transitive grouping.
After chunk A is compared against all later chunks, its entries are `del`-ed from
`scan_cache`, capping live descriptors to at most 2 × 500 at any time.

For `"phash"`, `"orb"`, and `"siamese"` the cache is already small — no change
needed.

**Estimated saving: 100–500 MB** for SIFT/SSIM on large directories.

---

## Tier 2 — Medium impact, medium effort

---

### 3 · _loaded_results_buffer accumulates QPixmaps before render

`gui/src/tabs/database/scan_metadata_tab.py:83`

```python
self._loaded_results_buffer: List[Tuple[str, QPixmap]] = []
```

Worker signals append `(path, QPixmap)` tuples at line 1120.  The buffer is
flushed to the UI and cleared at line 560.  If the loader emits results faster
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

This halves peak buffer RAM.  If further reduction is needed, add a
`maxlen=500` deque and pause the worker when the deque is full.

**Estimated saving: 50–250 MB peak** during heavy database scans.

---

### 4 · Tag checkbox dicts scale linearly with database tag count

`gui/src/tabs/database/scan_metadata_tab.py:246`
`gui/src/tabs/database/search_tab.py:140`

```python
self.tag_checkboxes = {}   # one live QCheckBox per tag
```

Both tabs call `_setup_tag_checkboxes()` which queries all tags from the
database and creates one `QCheckBox` widget per tag.  The dict is replaced
wholesale on every refresh.  At small tag counts (< 500) this is negligible.
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

### 5 · source_path_to_widget map in ImageExtractorTab never shrinks

`gui/src/tabs/core/image_extractor_tab.py:72`

```python
self.source_path_to_widget: Dict[str, QWidget] = {}
```

This map holds a strong reference to each card widget for every processed
video.  Qt's `deleteLater()` cannot actually free the C++ object while a
Python strong reference to the wrapper exists.  The result is that card widgets
for off-screen pages accumulate silently.

**Fix**

Pop entries from `source_path_to_widget` in the same loop that removes widgets
from the layout during page changes (mirror the pattern in
`AbstractClassTwoGalleries.refresh_found_gallery`).

---

### 6 · ML model weights stay resident after the feature is used

**SiameseModelLoader** (`backend/src/models/siamese_network.py:14`)
Class-level singleton: `_model = None`.  On first call to `get_embedding()`,
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
completes.  The model reloads on next use (one-time ~2 s delay).

For training runs (GAN), no change is needed — keeping weights in RAM during
an active training session is expected.

**Estimated saving: 45–200 MB** while the feature is not actively in use.

---

## Tier 3 — Small impact, structural hygiene

---

### 7 · Signal lambda closures capture strong widget references

`gui/src/classes/abstract_class_two_galleries.py:484`

```python
worker.signals.result.connect(
    lambda p, px: self._on_selected_image_loaded(p, px, target_widget)
)
```

The lambda captures `target_widget` (a `QWidget`) by strong reference.  If the
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

### 8 · PostgreSQL queries materialise full result sets

`backend/src/database/image_database.py`

`cursor.fetchall()` loads entire result sets into Python lists.  For queries
bounded by a small `LIMIT` (e.g. nearest-neighbour search returning 10 rows)
this is fine.  For bulk export queries or queries that could return thousands
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

### 9 · open_queue_windows and open_image_preview_windows are list-bounded

`gui/src/tabs/core/wallpaper_tab.py:176–177`

```python
self.open_queue_windows: List[QWidget] = []
self.open_image_preview_windows: List[QWidget] = []
```

The lists are properly cleaned in the `closeEvent` (lines 761–769) and via
callbacks when windows close (lines 885–912).  However, if a user repeatedly
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

## Memory budget summary

| Source | Worst-case before | After all fixes |
|---|---|---|
| Gallery base-class caches (✅ done) | Unbounded QPixmap | ~100 MB (3 × LRU cap) |
| WallpaperTab / ImageExtractorTab / ReverseSearchTab caches | Unbounded QPixmap | ~75 MB (inherited LRU) |
| DuplicateScanWorker.scan_cache (SIFT, 10 k images) | ~100–500 MB | ~10 MB per chunk |
| _loaded_results_buffer peak | Unbounded QPixmap | ~5 MB (QImage + optional deque cap) |
| tag_checkboxes (5 000 tags × 2 tabs) | ~10–40 MB | < 1 MB (QListWidget virtual) |
| Siamese ResNet-18 + GAN weights (idle) | 45–200 MB | 0 MB (unload on finish) |
| source_path_to_widget widget leak | Grows per session | Eliminated |
| **Total (active 10 k-image session)** | **800 MB – 3 GB** | **~200–300 MB** |

---

## Verification checklist

After implementing each tier:

1. Launch the app and log in.
2. Open Convert tab → browse a directory with 500+ images → page through 5+ pages
   forward and back.  Observe Python RSS in `htop`.
3. Open Wallpaper tab → add 500+ images to the queue.  Observe RSS.
4. Run duplicate scan with SIFT on a 1 000-image directory.  Observe peak RSS.
5. Run `pytest` — no regressions expected.
