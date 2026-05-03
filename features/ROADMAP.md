# Image-Toolkit Advanced Roadmap

## Overview

This roadmap defines the feature evolution and quality-of-life improvements for the Image-Toolkit ecosystem. It is grounded in a deep audit of the current codebase (May 2026) and covers every layer of the stack.

The application follows a **Tri-Interface Strategy**:
1. **PySide6 Desktop App** — The heavyweight native powerhouse for local ML inference, deep OS integration, and interactive image pipeline control.
2. **React / Tauri Web App** — The cross-platform, network-ready hub for library management, remote task dispatch, and device syncing.
3. **Android / iOS Mobile Apps** — Companion clients for remote monitoring, on-device preview, and library browsing.

Each item is tagged by priority: **[CRITICAL]**, **[HIGH]**, **[MEDIUM]**, or **[LOW]**.

---

## 1. PySide6 Desktop Application (The Pro Environment)

### A. Advanced ML UI & Interactive Pipelines

#### [CRITICAL] SD3 ControlNet & IP-Adapter Support
`backend/src/models/sd3_wrapper.py:62` has a `TODO` for ControlNet. Switch the pipeline to `StableDiffusion3ControlNetPipeline` when a ControlNet model path is provided. In `DDMGenerateTab`, add a ControlNet image drop-zone, conditioning scale slider, and preprocessor selector (Canny, Depth, OpenPose). Separately, add IP-Adapter support via `diffusers`' `IPAdapterMixin` for reference-image conditioning — expose a reference image input and weight slider. Both unblock character-consistency and pose-guided workflows on the SD3 backbone.

#### [CRITICAL] Complete CLI Dispatcher Commands
`backend/src/controller/dispatcher.py` has three disconnected dispatch paths: merge (line 56), database (line 91), and model (line 95) all either print a placeholder or are unreachable. Wire all three so the app is fully scriptable from the command line. The `--recursive` flag for batch conversion (line 46) also needs to be forwarded to `ImageFormatConverter.convert_batch()`.

#### [HIGH] Dynamic ComfyUI Dashboard
Build a native PySide6 dynamic form generator that parses `workflow_api.json` templates (like the 7-stage Illustrious XL pipeline in `backend/config/inference/sdxl_comfyui.yaml`) and auto-generates UI controls — sliders, dropdowns, seed spinboxes, and node-selection widgets — mapped to `parameters.json` keys. The `ComfyGenerateTab` currently requires hand-editing raw JSON; this replaces it with a generated form that calls the ComfyUI API transparently. Add a template browser to save, load, and share workflow presets.

#### [HIGH] Panorama Stitch UI (`StitchTab`)
Create a dedicated `StitchTab` using `QGraphicsView` to expose `stitch_net.py` and `loftr_wrapper.py` interactively. Users should be able to load two or more frames, preview LoFTR keypoint matches as an overlay, drag alignment anchors to correct stitching errors before rendering, preview the "Master-Cel" masking boundaries from `anime_stitch_pipeline.py`, and export stitched panoramas at up to 4× source resolution via `image_merger.rs`. Queue batch stitch jobs and monitor them via the existing `QThreadPool` worker pattern.

#### [HIGH] Interactive Background Removal (BiRefNet Integration)
Integrate `birefnet_wrapper.py` into the `ConvertTab` as an optional post-processing step. After format conversion, a "Remove Background" toggle passes each output image through BiRefNet. Add an interactive mask-refinement widget using QPainter brush strokes to correct matting errors before saving. Output alpha channel as transparent PNG. Run as a `QRunnable` to keep the main thread free.

#### [HIGH] Full Fine-Tune UI Tab (`FullFTTrainTab`)
`backend/src/models/full_finetune.py` exists but has no dedicated GUI tab. Add a `FullFTTrainTab` with dataset path, gradient checkpointing toggle, batch size, mixed precision selector, and DeepSpeed ZeRO stage selector. The `LoRATrainTab` partially covers this; full fine-tuning of SDXL/Flux needs its own surface.

#### [HIGH] Flux Dev Generation Tab
`backend/config/model/flux_dev.yaml` is configured but there is no dedicated generation tab for `FLUX.1-dev`. Extend the `DDMGenerateTab` model selector to include Flux, routing to a `FluxPipeline` backend path. Expose its unique CFG-free distilled guidance scale and step count parameters as first-class controls, not buried in an advanced JSON field.

#### [MEDIUM] DreamBooth Prior Preservation Training
`backend/config/training/dreambooth.yaml` exists but prior preservation loss is not surfaced in `LoRATrainTab`. Add a "DreamBooth Mode" toggle that unlocks a class images directory selector, prior loss weight slider, and num-class-images field. Wire these into `DreamBoothTuner.train()`.

#### [MEDIUM] Multi-GPU Training via Accelerate
Current training runs on a single device. Add Accelerate config generation into training tabs. When multiple CUDA devices are detected, expose a device-selection multi-check and auto-write an `accelerate_config.yaml`. Pass `--multi_gpu` to the training pipeline. Essential for multi-stage LoRA training on the 3090 Ti alongside other CUDA workloads.

#### [MEDIUM] R3GAN Evaluate Tab — Live Loss Curve Visualization
`r3gan_evaluate_tab.py` only shows scalar metrics. Embed a `pyqtgraph` line chart that reads from `training_hooks.py` diagnostics and plots discriminator loss, generator loss, and FID over epochs in real time during training.

#### [MEDIUM] LyCORIS / DoRA Method Selector
`lora_diffusion.py` supports LoCon, LoHa, LoKr, DoRA, and rsLoRA via PEFT but the `LoRATrainTab` only exposes a fraction of these. Add a method selector dropdown that surfaces all available PEFT methods with a brief description tooltip. Show the relevant method-specific hyperparameters (e.g., LoCon convolution dimension) only when that method is active.

#### [LOW] Video Wallpaper with mpv
Expand `WallpaperTab` to support video wallpapers. On Linux, manage an `mpv` subprocess alongside the existing `qdbus-qt6` D-Bus wallpaper daemon. On Windows, use the existing COM pathway. Add seamless-loop detection and per-monitor assignment. Use subprocess-based mpv (not libmpv) to avoid native C++ library conflicts with the JPype JVM.

#### [LOW] Training Run History Browser
Add a training history panel to `TrainTab` that reads checkpoint directories and surfaces: model name, architecture, dataset path, epoch count, final loss values, and sample generation grid. Let users resume a past run, compare metrics across runs, or delete old checkpoints with a single click.

---

### B. OS Integration & Media Handling

#### [HIGH] Hardware-Accelerated Frame Extraction
Replace `cv2.VideoCapture` in the `ImageExtractorTab` and `task_extract_frames()` with a Rust-native FFmpeg binding. Add `base/src/core/video_extractor.rs` using the `ffmpeg-next` crate for hardware-decode support (NVDEC, VAAPI). Expose via PyO3 as `base.extract_frames(path, output_dir, start_ms, end_ms, fps_limit, hw_device)`. This will be dramatically faster than OpenCV for high-resolution H.264/H.265 sources.

#### [HIGH] Video Converter — Quality & Codec Controls
`base/src/core/video_converter.rs` is skeletal. Build it out with CRF/bitrate selection, hardware encode (NVENC, VAAPI), audio track control (copy / re-encode / strip), and a full container format matrix (mp4, mkv, webm, mov). Surface all options in a `VideoConvertTab` alongside the existing image conversion workflow.

#### [MEDIUM] System Tray Integration & Daemon Mode
Add a `QSystemTrayIcon` so the desktop app runs in the background while the slideshow daemon and wallpaper rotation are active. The tray menu should expose: pause/resume slideshow, add wallpaper folder, open main window, and quit. The slideshow daemon (`base/src/utils/slideshow_daemon.rs`) already runs as a separate process — the tray is the missing control surface.

#### [MEDIUM] Drag-and-Drop Desktop Integration
Enable OS-level drag-and-drop targets for all conversion, merge, and extraction tabs. Accept `text/uri-list` and `application/x-qabstractitemmodeldatalist` mime types so users can drag files directly from a file manager into gallery panels, bypassing the directory picker entirely.

#### [MEDIUM] Batch Rename with Pattern Templates
Add a `RenameTab` or toolbar action that applies pattern-based renames to selected files. Support tokens: `{index}`, `{date}`, `{resolution}`, `{group}`, `{tag}`, `{hash}`. Preview the rename mapping in a before/after table before committing. Support undo via the edit recipe system.

#### [LOW] macOS Wallpaper Support
Add a macOS variant for wallpaper setting using `NSWorkspace.setDesktopImageURL(_:for:options:)` via a small Swift helper binary. Guard it behind `sys.platform == "darwin"` in `backend/src/core/wallpaper.py`.

---

### C. Gallery & Image Management QoL

#### [HIGH] Non-Destructive Edit Recipes
Implement an edit-history JSON format for color grade, crop, and resize. Rather than overwriting source pixels, store a `recipe.json` sidecar per image listing ordered operations with parameters. Apply the recipe chain in memory on open. "Bake" to disk only on explicit export (`Ctrl+E`). Support recipe sharing by exporting the JSON. Requires a `RecipeEngine` class in the backend and a `RecipeEditor` panel in `ConvertTab`.

#### [HIGH] Intelligent Duplicate Grouping with Visual Diff
Enhance `DuplicateFinder` to present near-duplicate collisions side-by-side:
- Pixel-level diff heatmap via OpenCV `absdiff()`.
- File metadata comparison (size, resolution, format, date) alongside the diff.
- Batch resolution actions: "Keep Largest", "Keep Newest", "Keep All Non-Watermarked" (using BiRefNet to detect watermark regions).
- Wire into the existing `PropertyComparisonDialog` component in `gui/src/components/`.

#### [HIGH] Global Keyboard Shortcuts & Command Palette
Add a command palette (`Ctrl+K`) with fuzzy-searchable access to all tab actions. Implement `QShortcut` bindings:
- `Ctrl+O` — Open directory picker in active tab.
- `Ctrl+Enter` — Run the active tab's primary action.
- `Ctrl+Z` / `Ctrl+Shift+Z` — Undo/Redo for edit recipes.
- `Space` — Toggle full-screen preview.
- `Delete` — Delete selected items with confirmation.
- `Ctrl+F` — Focus the search field.

#### [HIGH] Session State Persistence
Tab state (input paths, parameters, selected files) is lost on restart. Add a `SessionManager` that serializes all tab state to JSON on `QApplication.aboutToQuit` and restores it on launch. Include a configurable MRU list (last 10 paths) per tab.

#### [HIGH] Gallery Multi-Select with Batch Actions Toolbar
When multiple images are selected: show a floating action toolbar with Convert, Delete, Add to Group, and Export Captions actions. Add rubber-band marquee selection (click-drag), `Ctrl+A` to select all, `Ctrl+Shift+A` to invert selection.

#### [MEDIUM] Configurable Thumbnail Size Slider
Add a thumbnail size slider (64px → 512px) in the gallery toolbar that dynamically resizes thumbnails without reloading from disk. The `LRUImageCache` stores full `QImage` — use `QPixmap.fromImage().scaled()` at render time for instant resize.

#### [MEDIUM] Image Preview Enhancements
Expand `image_preview_window.py` to support pan and zoom (mouse wheel + drag), side-by-side A/B comparison mode (original vs. processed), EXIF/XMP metadata panel toggle, copy-to-clipboard shortcut, and "Open in external editor" action.

#### [MEDIUM] Unified Progress Overlay
Replace per-tab progress widgets with a unified bottom-anchored `ProgressOverlay` panel showing: a progress bar per active operation with label, ETA, and cancel button; a badge count on each tab's header showing pending/running operations; a notification bell for completions.

#### [MEDIUM] Dark/Light Theme Toggle
Add a theme toggle in `SettingsWindow`. Implement `dark.qss` and `light.qss` stylesheets applied via `QApplication.setStyleSheet()`. Persist the choice in the config file. Default to the system color scheme via `QGuiApplication.palette()`.

#### [LOW] LRU Cache Size Configurability
`gui/src/utils/lru_image_cache.py` hardcodes cache sizes (found=300, selected=200, single=300). Expose these in `SettingsWindow` with a memory usage readout in the status bar. Users with limited RAM can reduce; users with 32GB+ can increase for snappier gallery navigation.

#### [LOW] Onboarding & First-Launch Wizard
A `FirstLaunchWizard` dialog that guides new users through: setting the local source path, testing the PostgreSQL connection, unlocking VaultManager credentials, and selecting the default wallpaper folder.

---

## 2. Tauri / React Web App (The Cross-Platform Hub)

### A. Real-Time Network Architecture

#### [CRITICAL] Django Channels / WebSocket Live Progress
Upgrade the REST-only API to include WebSocket endpoints via Django Channels. Define a `TaskProgressConsumer` that forwards Celery progress events to the browser. Add a React `useTaskProgress(taskId)` hook that drives a live progress bar, ETA display, and stdout log stream for all long-running operations — batch conversion, crawling, training.

#### [HIGH] Virtualized Media Galleries
All gallery queries currently load entire result sets into the DOM. Implement `@tanstack/react-virtual` as the scroll engine for `WallpaperGallery` and every search result list. Fetch paginated slices from Django (page size 100), pre-fetch the next page on scroll, and dispose offscreen tiles. Essential for 100,000+ image libraries.

#### [HIGH] Missing API Endpoints
Several backend capabilities have no REST surface at all. Add:
- `GET /api/status/<task_id>/` — Celery task progress polling.
- `DELETE /api/tasks/<task_id>/` — Celery task cancellation.
- `GET /api/db/groups/` — List all groups and subgroups.
- `GET /api/db/search/` — Semantic vector search with query, filters, and pagination.
- `GET /api/db/stats/` — Image count, group count, vector coverage.
- `POST /api/db/embed/` — Trigger CLIP embedding for a given group or directory.
- `POST /api/train-lora/` — LoRA training task (only GAN training is wired today).
- `POST /api/run-birefnet/` — Batch background removal.
- `POST /api/stitch/` — Panorama stitching pipeline.

#### [HIGH] Saved Search Presets & History
Add a `SavedSearch` model and endpoints (`POST /api/search/presets/`, `GET /api/search/presets/`). In the React `SearchTab`, render a sidebar of saved searches that can be re-run or edited. Store the last 50 searches in `localStorage` as a quick-access history.

#### [MEDIUM] Batch Operation Pipeline Builder
Add a workflow-style drag-and-drop pipeline composer in the React frontend. Users build a sequence of operations (Crawl → Convert → Embed → Tag) into a named pipeline, then trigger it as a Celery `chain()`. Add a `POST /api/pipeline/` endpoint. The Celery primitive already supports chaining; the frontend just needs the composition UI.

#### [MEDIUM] LAN Remote Access Mode (mDNS)
Register the service as `_imagetoolkit._tcp.local` using the `zeroconf` Python library. Bind Django to `0.0.0.0` with token authentication. Display the LAN URL and QR code in the desktop app's `SettingsWindow` so mobile clients can connect without manual IP configuration.

#### [LOW] Progressive Web App (PWA) Manifest
Add a `manifest.json` and service worker to the React frontend so the web app can be installed as a PWA on desktop and Android Chrome. Cache the app shell and static assets, and implement a background-sync queue for offline task submission that drains when the connection restores.

---

### B. UI & UX QoL

#### [HIGH] Dark Mode & Theme System
Add CSS custom properties (design tokens) for colors, spacing, and typography. Implement `prefers-color-scheme` auto-detection and a manual toggle stored in `localStorage`. All components should reference token variables rather than hardcoded hex values.

#### [HIGH] Virtual Album Browser
Add a "Virtual Albums" section to the `DatabaseTab` backed by live HNSW vector queries. Users type a natural language query (e.g., *"cyberpunk cityscapes at night with rain"*) and save it as a named album. The album auto-refreshes on a configurable schedule and shows a live image count badge. Render albums as a special group type distinct from manually curated groups.

#### [MEDIUM] Image Detail Panel (Slide-In)
When clicking any image in a gallery, slide in a detail panel (rather than a separate page) showing: full-size preview, EXIF metadata, tags, group membership, vector embedding visualization (a 2D UMAP projection of the image's neighbors), edit recipe history, and quick actions (Delete, Convert, Add to Group).

#### [MEDIUM] Keyboard Navigation Mode
Add a `useHotkeys` hook via `react-hotkeys-hook` replicating the desktop keyboard shortcuts in the web frontend. Arrow keys to navigate gallery, `Enter` to open detail panel, `Delete` to remove, `Space` to preview full-screen. Essential for power users managing large libraries from the browser.

#### [LOW] Localization (i18n) Foundation
Add `react-i18next` and extract all user-visible strings into `en.json` translation files. Structure the codebase so adding a new language requires only a new JSON file. Prioritize the Convert, Search, and Database tabs first.

---

## 3. Core Engine & AI Enhancements (Rust / Python Base)

### A. Next-Generation AI Tagging & Search

#### [HIGH] VLM Auto-Tagging Pipeline
`backend/src/models/data/captioner.py` exists — build a full `VLMCaptioner` class on top of it backed by `Moondream2` or `LLaVA-1.5-7B-GGUF` (via `llama-cpp-python` for CPU / `transformers` for GPU). Run captioning as a background `QRunnable` after images are added to the database. Store captions in a new `captions` column. Surface captions as searchable metadata in `SearchTab` and as auto-populated tags in `DatabaseTab`. Add a "Re-caption All" batch task in `ScanMetadataTab`.

#### [HIGH] Smart Semantic Albums
Implement dynamic virtual albums backed by live `pgvector` HNSW queries. A `VirtualAlbum` table stores a natural-language query string, threshold, and cached member list. The `SearchTab` gains a "Save as Album" button. Albums auto-refresh on a configurable schedule (hourly or on new image ingestion). Pairs with the React Virtual Album Browser feature above.

#### [HIGH] HNSW Index Migration
Transition all `pgvector` `vector` columns from `ivfflat` to `hnsw` index type. This reduces similarity search latency from seconds to milliseconds at 100k+ image scale. Requires a new Django migration that drops the existing IVFFlat index and creates the HNSW index with `(m=16, ef_construction=64)`. Update `image_database.py` to set `hnsw.ef_search = 100` per query.

#### [MEDIUM] Perceptual Hash Completion
`task_scan_duplicates()` in `tasks/tasks.py` returns an empty `{}` placeholder for perceptual hash mode. Implement the full pipeline: compute pHash/dHash via the Rust `image_finder.rs` (which already has exact hash support), build a hamming distance matrix, and cluster images with distance ≤ threshold. Return grouped clusters, not a flat list.

#### [MEDIUM] CLIP Ensemble Search
Support multiple CLIP variants (OpenAI ViT-L/14, MetaCLIP ViT-H/14, SigLIP) stored as separate `vector` columns. Let users select the embedding model at search time, or enable an ensemble mode that averages cosine distances across all available models. Store the model identifier per embedding row so the database supports heterogeneous embedding sources.

#### [LOW] Hybrid Text + Vector Search
Add a `tsvector` GIN index over the captions and tags columns. Extend `SearchTab` to support hybrid search: cosine similarity from the vector column merged with `ts_rank` full-text relevance. This covers keyword-based search for users who don't have an embedding query in mind.

---

### B. Database Performance & Indexing

#### [HIGH] Asynchronous Bulk Ingestion
Refactor `image_database.py` batch insertion to use `psycopg2.extras.execute_values()` with a single round-trip instead of per-row inserts. For very large directories (50,000+ images), add a `COPY FROM STDIN` path using `psycopg2.copy_expert`. Current single-insert path takes ~0.3s per 100 images; bulk should achieve < 0.05s per 100.

#### [MEDIUM] Incremental Embedding — Skip Already-Embedded Images
Add an `is_embedded` boolean column to the images table. During embedding passes, `SELECT ... WHERE is_embedded = FALSE`, process in batches, and flip the flag on success. This makes repeated scans of large libraries O(new images) rather than O(all images).

#### [MEDIUM] SafeTensors Model Inspector
`backend/src/utils/safetensors_metadata.py:80` has a silent `pass` in its metadata parsing. Complete the implementation to read LoRA rank, alpha, target modules, and trigger words from safetensors headers. Surface this as a model inspector panel in `MetaCLIPInferenceTab` and `LoRAGenerateTab` — users should be able to inspect a trained model's metadata without loading it into VRAM.

---

### C. Rust Core Optimizations

#### [HIGH] Streaming Image Processing
`base/src/core/image_merger.rs` and `image_converter.rs` load full `DynamicImage` buffers before processing. The benchmark shows a 734MB peak for thumbnail generation. Refactor both to tile-based streaming: process output canvas rows in chunks and write to `BufWriter<File>` directly. Use `image::io::Reader`'s decoder API for scanline-chunk decoding on JPEG, PNG, and TIFF. Target ≤ 200MB peak RAM for a 1,000-image batch at 1080p.

#### [HIGH] Async HTTP Crawler in Rust
`base/src/web/image_crawler.rs` is Selenium-based and single-threaded for direct-URL jobs. Add a Tokio async runtime for non-JS crawls using `reqwest` + `tokio` with configurable concurrency. Reserve Selenium only for JS-rendered pages. This should improve direct-URL crawl throughput by ~10× and reduce WebDriver resource usage significantly.

#### [MEDIUM] Additional Image Board Crawlers
Extend the `image_board_crawler.rs` framework with new platform crawlers: Twitter/X media downloads, ArtStation gallery scraper, Pixiv (with OAuth), and Pinterest board downloader. Each should implement the `Crawler` trait and be selectable from the `ImageCrawlerTab` board-type dropdown.

#### [MEDIUM] Parallel Web Crawler Progress Reporting
The current crawlers run as opaque blocking operations with no mid-crawl feedback. Add a progress callback channel (Rust `mpsc::Sender`) that emits per-download events (URL, file size, local path) back to Python via PyO3, so the `ImageCrawlerTab` progress bar reflects real-time download count rather than a spinner.

---

## 4. Quality of Life & Utilities

#### [HIGH] Non-Destructive Edit Recipes *(Desktop)*
*(See Section 1C — full description there.)*

#### [HIGH] Intelligent Duplicate Grouping with Visual Diff *(Desktop + Web)*
*(See Section 1C — full description there.)*

#### [HIGH] Safetensors Model Inspector *(Desktop)*
Standalone tool accessible from any training or generation tab: drop a `.safetensors` file to inspect LoRA rank, alpha, trigger words, and base model compatibility. Show a preview generation using the loaded LoRA at 3 different strength values (0.5, 0.75, 1.0) side-by-side.

#### [HIGH] Batch Rename with Pattern Templates
Add a rename tool (tab or toolbar action) that applies pattern-based renames to selected files. Support tokens: `{index}`, `{date}`, `{resolution}`, `{group}`, `{tag}`, `{hash}`. Preview the rename mapping in a before/after table before committing. Support undo via the edit recipe system.

#### [MEDIUM] Quick-Convert Context Menu in Gallery
Right-clicking any image in any gallery should show a context menu with "Quick Convert To…" sub-items (PNG, JPEG, WebP, AVIF). Each item immediately fires a single-file conversion without opening the `ConvertTab`. The output lands in the same directory with a user-configurable suffix.

#### [MEDIUM] Aspect Ratio Crop Assistant
Add a crop-to-ratio helper in `ConvertTab` that lets users specify a target aspect ratio (e.g., 16:9, 1:1, 3:4, SDXL 1024×1024) and shows a crop preview overlay on the source image. The crop anchor (top-center, center, face-detect) is selectable. Face-detection crop uses the existing Siamese network's face-embed pipeline.

#### [MEDIUM] Image Metadata Batch Editor
Add a metadata editor tab that can write EXIF/XMP fields (title, description, keywords, copyright, GPS) to a batch of selected images. Support "copy metadata from one image to many" for quick-tagging datasets. Wire into the `ScanMetadataTab` workflow.

#### [MEDIUM] Color Palette Extractor
Add a palette extraction feature accessible from image preview and `SearchTab`. Extract the N dominant colors from an image using k-means (backed by the Rust core). Show swatches with hex values and copy-to-clipboard. Add "Search by Color" functionality that encodes the dominant palette into a query vector for pgvector similarity search.

#### [MEDIUM] Slideshow Queue Editor
The `SlideshowWindow` and `slideshow_daemon.rs` exist but queue management is basic. Add a queue editor panel with drag-to-reorder, per-image duration overrides, transition type selector (fade, cut, slide), and a "play from here" action on any item.

#### [LOW] Export Dataset Manifest
From `DatabaseTab`, add an "Export Dataset" action that writes a JSONL or CSV manifest of all images in a group or subgroup, including paths, tags, captions, and embedding norms. This feeds directly into `lora_dataset.py` and external training tools without manual file organization.

#### [LOW] Image Statistics Dashboard
A stats tab or panel showing library-wide metrics: total image count, format breakdown, resolution distribution histogram, tag frequency chart, last-crawled timestamps per source, and VRAM/RAM usage by the active model. Pull data from `GET /api/db/stats/` and render with `pyqtgraph` (desktop) or Recharts (web).
