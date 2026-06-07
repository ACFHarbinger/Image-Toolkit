# New Features Roadmap — Capabilities and Integrations

*Last updated: 2026-05-31.*

---

## How to Use This Document

Each section describes a proposed feature, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping.

---

## 4.1 Batch Stitching

**Pain point:** Users with large screenshot libraries (e.g., 50+ groups of frames from novel-reading sessions) currently process each group one at a time in the StitchTab.

### Options

**A — Directory-level batch mode (GUI)**
Scan a root directory for subdirectories matching a naming pattern (e.g., `scene_*/`). Run the ASP pipeline on each, save outputs to a `stitched/` subfolder. Show a batch progress list in the StitchTab with per-item status, ETA, and output preview.
- Pros: No external tooling. Best experience for non-technical users.
- Cons: Long-running GUI operation. Requires cancellable QThread with item-level progress (§2.7).

**B — PostgreSQL-backed persistent queue**
A `stitch_jobs` table in the existing database where each row is a frame group. Workers process items in order. The queue survives app restarts. Expose via the database tab or a dedicated Job Queue tab.
- Pros: Queue survives crash/restart. Enables priority and retry.
- Cons: Significant schema + UI effort. Overkill for single-user desktop app.

**C — CLI batch mode [Quick Win]**
`python main.py stitch --batch-dir /path/to/groups/`. Iterates subdirectories, runs ASP on each, writes outputs. Suitable for scheduled/overnight runs via cron or systemd.
- Pros: Leverages existing `argparse` infrastructure. Fast to implement. Works headlessly.
- Cons: No GUI progress. No persistent state if interrupted.

**D — File system watcher**
Use `watchdog` (Python) or `notify` (Rust, via `inotify`) to watch a directory. When a new subdirectory appears (e.g., a screen recording session ends), automatically enqueue it for stitching.
- Pros: Fully automatic; zero user interaction for recurring workflows.
- Cons: Requires `watchdog` dependency. Auto-trigger may stitch incomplete captures if recording is still in progress.

**E — Batch mode with resume support**
Extend C with a `results.json` that records which groups have been processed. Re-running with `--resume` skips completed groups. Handles interrupted overnight runs.
- Pros: Resilient to crashes. Trivial to add on top of C.
- Cons: JSON state file must be kept consistent with filesystem.

**Recommendation:** C first (leverages existing infrastructure). E immediately after. A as a GUI counterpart once C is validated. D for power-user automation workflows.

---

## 4.2 Export Stitched Panorama to Scrolling Video

**Pain point:** Stitched manga/visual novel pages are long-form content users may want to share as videos (e.g., on platforms that don't support long images). A scrolling video export is a natural derived product.

### Options

**A — OpenCV VideoWriter with pan-and-scan**
Crop a sliding window across the panorama and write each position as a video frame. Parameterise scroll speed (px/frame) and output resolution.
- Pros: Zero new binary dependencies. Quick to prototype.
- Cons: Limited codec support (MJPEG, XVID). No hardware encoding. Lower quality than ffmpeg.

**B — FFmpeg pipe from Python/Rust**
Pipe frame bytes to `ffmpeg` via subprocess stdout. Handles codec selection (H.264, H.265, AV1), hardware encoding (NVENC, VAAPI), and container formats (MP4, WebM).
- Example: `ffmpeg -f rawvideo -pix_fmt rgb24 -s {W}x{H} -r {fps} -i pipe: -c:v libx264 out.mp4`
- Pros: High quality. Hardware-accelerated encoding. No Python video library needed.
- Cons: Requires `ffmpeg` binary on PATH. Not bundled with PyInstaller by default (needs separate inclusion).

**C — Export as animated WebP (small panoramas)**
For panoramas < 1500px wide, `imageio` + `PIL` can produce a looping animated WebP. Zero new binary dependencies.
- Pros: Quick-share option. Self-contained.
- Cons: Animated WebP support limited in some browsers/viewers. Poor compression for large panoramas.

**D — GIF export (legacy compatibility)**
Use `PIL.Image.save(..., format='GIF', save_all=True, append_images=...)` for a looping GIF.
- Pros: Universal compatibility.
- Cons: 256-colour palette. Large file sizes. Poor quality for complex images.

**E — Configurable scroll parameters (easing, hold at ends)**
Extend A/B with configurable easing (linear, ease-in-out), pause at start/end, and audio track attachment.
- Pros: Polished output for sharing.
- Cons: Adds complexity. Best as a follow-on once basic export works.

**Recommendation:** B for full-resolution output (most portable quality path). C as a quick-share option. E as a polish layer on top of B.

---

## 4.3 CLIP-Based Semantic Image Search

**Pain point:** The database supports vector search via pgvector, but embeddings are ResNet-18 Siamese features tuned for duplicate detection, not semantic content. No natural-language query capability exists.

### Options

**A — OpenCLIP (open_clip_torch) text + image encoder**
Generate CLIP embeddings during database ingest. Store a second embedding column (e.g., `clip_embedding vector(512)`) in PostgreSQL. Support both text queries ("red sunset background") and image similarity queries.
- `open-clip-torch` is pip-installable, no API key required. Supports ViT-B/32, ViT-L/14, and larger.
- Processing speed: ~7 images/second on a GPU (cloud L4 benchmark).
- Pros: State-of-the-art semantic understanding. No external API dependency.
- Cons: Second embedding column doubles storage. Separate HNSW index needed.
- Reference: [open_clip GitHub](https://github.com/mlfoundations/open_clip)

**B — AnimeCLIP / WaifuDiffusion CLIP fine-tune**
Use a domain-specific CLIP variant fine-tuned on anime content (e.g., `ViT-B/16` fine-tuned on Danbooru) for better semantic accuracy on the primary use case.
- Pros: Higher accuracy for anime/manga content vs. general CLIP.
- Cons: Model requires separate download. Fine-tuned models may have less coverage for non-anime images.

**C — Dual-column search (Siamese + CLIP)**
Run both Siamese (duplicate detection) and CLIP (semantic similarity) embeddings in parallel. Show results from both in the search tab with a toggle.
- Pros: Preserves existing duplicate detection functionality alongside new semantic search.
- Cons: Two HNSW indexes to maintain. Higher storage cost.

**D — Multimodal re-ranking**
First retrieve top-50 candidates via CLIP, then re-rank using the Siamese embedding for visual similarity within the candidate set. Best of both.
- Pros: Better precision than either alone.
- Cons: Two-stage retrieval adds latency. Complex query pipeline.

**E — FAISS as a local in-memory index**
For collections that don't need persistent storage, use FAISS (`faiss-cpu` or `faiss-gpu`) as an in-memory vector index alongside pgvector.
- Pros: Faster query latency than pgvector for billion-scale collections.
- Cons: Index must be rebuilt on restart. Redundant if pgvector is already tuned (§3.4D).

**Recommendation:** A as the initial implementation. B as a model swap once A is validated. C for users who want both capabilities simultaneously.

---

## 4.4 Auto-Tagger Integration

**Pain point:** The database supports tags, but tagging is entirely manual. Crawlers fetch Danbooru/Gelbooru tags for downloaded images, but locally-sourced images have no tags.

### Options

**A — WD-1.4 (WaifuDiffusion Tagger) via ONNX**
Run the ONNX model locally on each image during database ingest. Generates booru-style tags at ~50–100ms/image on CPU, faster on GPU.
- 13 WD model variants available (v1, v2, v3; ViT, SwinV2, ConvNext).
- ONNX Runtime is already a likely dependency via BiRefNet.
- Reference: [WD Tagger HuggingFace Space](https://huggingface.co/spaces/SmilingWolf/wd-tagger); [wd14-tagger-server GitHub](https://github.com/LlmKira/wd14-tagger-server)
- Pros: Best accuracy for anime/manga content. Booru-compatible tags integrate naturally with existing tag schema. No internet required.
- Cons: Model download (~300 MB). ONNX Runtime dependency.

**B — MetaCLIP / CLIP-ViT zero-shot classification**
Use zero-shot classification against the full Danbooru tag vocabulary (50k+ tags) with CLIP. No separate tagger model needed if CLIP (§4.3A) is already present.
- Pros: No additional model if CLIP is installed.
- Cons: Much lower accuracy than WD-1.4 for domain-specific tags. Slow for large tag vocabularies.

**C — Human-in-the-loop tagging queue**
Show untagged images in a review queue. Present top-N auto-tag suggestions (from A or B) as checkboxes. User confirms or corrects. Persistent queue backed by PostgreSQL.
- Pros: Quality control — don't fully automate without review. Generates high-quality labelled data for future fine-tuning.
- Cons: Requires building a new UI component (tag review queue tab or panel).

**D — Batch background ingest tagger**
Run WD-1.4 as a background Celery task triggered on database ingest. Tags are stored as `pending_review` status until confirmed.
- Pros: Non-blocking ingest. Tags available quickly.
- Cons: Requires Celery worker to be running. `pending_review` status adds schema complexity.

**E — Tag confidence thresholds**
Allow configuring a minimum confidence threshold (e.g., 0.35). Only tags above the threshold are applied automatically; lower-confidence tags go to the human review queue (§C).
- Pros: Reduces false positives. Already a standard feature of WD tagger implementations.
- Cons: Threshold needs tuning per content type.

**Recommendation:** A for accuracy. C for quality control. E to tune the boundary between automatic and human review. D for large collections where blocking ingest is impractical.

---

## 4.5 Multi-Monitor Wallpaper Support

**Pain point:** Wallpaper tab sets wallpaper on the primary monitor via `qdbus-qt6`. Multi-monitor users want per-monitor control.

### Options

**A — KDE per-monitor wallpaper via D-Bus**
Enumerate monitors with `QScreen.availableScreens()`. For each screen, call the Plasma `org.kde.PlasmaShell` D-Bus method with the screen identifier.
- KDE 6 D-Bus API: `org.kde.PlasmaShell.setWallpaper(screen_id, plugin_id, config_object)`.
- Pros: Native KDE support. Already have `qdbus-qt6` integration.
- Cons: KDE-specific. GNOME requires a completely different approach.

**B — GNOME composited wallpaper**
GNOME doesn't natively support per-monitor wallpapers without extensions. Fall back to a composited image: stitch multiple source images side-by-side to match the total multi-monitor resolution and set as a single wallpaper.
- Tools: `xrandr` for screen geometry; PIL/Rust for image compositing.
- Pros: Works without GNOME extensions.
- Cons: Images must be manually aligned to screen boundaries. Composited image is static (no independent rotation per screen).

**C — Virtual desktop rotation (per-monitor scheduling)**
Rotate through different wallpaper categories per monitor on a configurable schedule. Each monitor gets a different image from its assigned queue.
- Pros: Diverse multi-monitor aesthetic without per-monitor wallpaper API.
- Cons: Requires per-monitor queue management in the UI.

**D — HydraPaper / Superpaper integration (GNOME)**
Call the HydraPaper or Superpaper CLI for GNOME multi-monitor support. These tools specifically solve the GNOME per-monitor wallpaper problem.
- Pros: Best GNOME experience. Well-maintained tools.
- Cons: External binary dependency. User must have HydraPaper/Superpaper installed.

**E — Wallpaper mirroring across all monitors**
Simplest mode: apply the same wallpaper to all monitors simultaneously. Already mostly implemented.
- Pros: No new complexity.
- Cons: Doesn't address the per-monitor request.

**Recommendation:** A for KDE (primary target given `qdbus-qt6`). B as GNOME fallback. D as the recommended path for GNOME power users who already have HydraPaper.

---

## 4.6 Image Deduplication Across Directories

**Pain point:** Duplicate detection operates within a single directory scan. Users with multiple collections (local, Dropbox, crawler downloads) accumulate cross-directory duplicates.

### Options

**A — Cross-directory phash index in PostgreSQL**
Store phash alongside the embedding on database ingest. Periodic deduplication job queries pairs with Hamming distance ≤ 4.
- SQL: `SELECT a.path, b.path FROM images a, images b WHERE a.id < b.id AND (a.phash <#> b.phash) <= 4`.
- Pros: Integrates cleanly with the existing database. No re-scanning.
- Cons: N² query complexity without an index. Requires a GiST index on the phash column or a batched comparison approach.

**B — Cross-directory duplicate scan GUI extension**
Extend the existing `DuplicateScanWorker` to accept multiple source directories as input. Results show which directory each duplicate is in, with options to keep-newer, keep-larger, or keep-all.
- Pros: Fastest UX path for users who don't use the database.
- Cons: In-memory comparison doesn't scale beyond ~50k images without the chunked approach already used.

**C — Locality-sensitive hashing (LSH) for near-duplicate detection**
Use LSH (e.g., `datasketch` MinHash LSH) to efficiently find near-duplicates across collections without N² comparisons.
- Pros: Sub-linear query complexity. Handles near-duplicates (resized, JPEG-recompressed versions).
- Cons: `datasketch` dependency. More complex than phash Hamming distance. LSH index must be rebuilt when collection grows.

**D — Differential sync deduplication**
When syncing from Dropbox/GDrive (§3.5-adjacent), compare incoming files against the local phash index before downloading. Prevents duplicates from entering the collection.
- Pros: Proactive deduplication at ingest.
- Cons: Requires the sync module to query the local database before committing downloads.

**Recommendation:** A integrates cleanly with the existing database. B is the fastest UX path if users don't use the database. C for near-duplicate detection at scale.

---

## 4.7 Slideshow Improvements

**Pain point:** Slideshow daemon exists (`base/src/utils/slideshow_daemon.rs`) but has minimal configuration. Users want timing, ordering, and filtering control.

### Options

**A — Configurable timing, order, and filter**
Expose interval (seconds), shuffle mode, and filter (by tag/group/source directory) as persistent settings in the wallpaper tab.
- Implementation: `slideshow_config.toml` loaded by the Rust daemon; UI sliders/dropdowns in the wallpaper tab persist to `QSettings`.
- Pros: Highest-value improvement. Direct user request.
- Cons: Requires Rust daemon + Python UI changes in sync.

**B — Tag-based playlist**
Define named playlists (e.g., "dark mode", "seasonal") as lists of tags. The slideshow plays images matching the active playlist.
- Pros: More granular control than directory-based filtering.
- Cons: Requires tag integration with the slideshow daemon.

**C — Time-of-day scheduling**
Different wallpaper categories at different times (bright mornings, dark evenings). Uses system time + sun position (optional, via `astral` for local sunrise/sunset).
- Pros: Ambient computing feature.
- Cons: `astral` dependency for sun-position mode. Edge cases around timezone/DST.

**D — Transition effects (fade, slide)**
Animate transitions between wallpapers by pre-rendering a short sequence and cycling the wallpaper in rapid succession via D-Bus.
- Pros: Polish.
- Cons: Requires D-Bus calls at ~30fps during transition (KDE may rate-limit). High effort for aesthetic-only improvement.

**E — Image health check before rotation**
Before advancing the slideshow, verify the next image is accessible and valid (exists, not corrupt). Skip to the next if not.
- Pros: Prevents blank/error wallpaper state. Defensive improvement.
- Cons: Adds a file check to the rotation loop.

**Recommendation:** A is the highest-value improvement. B as a follow-on for tag-aware playlists. C for ambient computing users. Skip D for now.

---

## 4.8 ComfyUI Workflow Integration for Post-Processing

**Pain point:** `comfy_generate_tab.py` and `comfy_manager.py` exist but are limited to generation. ComfyUI workflows could also be used for post-processing stitched outputs and gallery images.

### Options

**A — "Send to ComfyUI" button in StitchTab**
After stitching, allow loading the output into a pre-configured ComfyUI workflow (e.g., img2img cleanup, Real-ESRGAN upscale, inpainting).
- Implementation: POST to `http://localhost:8188/prompt` with the workflow JSON; poll `/history/{prompt_id}` for completion; load result via `/view?filename=...`.
- Reference: [ComfyUI Python API guide](https://apatero.com/blog/comfyui-workflow-to-production-api-deployment-guide-2025)
- Pros: High-quality post-processing using user's existing ComfyUI setup.
- Cons: Requires ComfyUI to be running. API calls are async — need status polling or WebSocket.

**B — ComfyUI as ASP post-processing backend**
Replace `anim/super_res.py` Real-ESRGAN path with a ComfyUI API call to a user-configured workflow. More flexible — any post-processing model the user has installed.
- Pros: Decouples ASP from specific model implementations. Users can swap models without code changes.
- Cons: ComfyUI must be running during ASP execution. Adds latency for the API round-trip.

**C — Drag-and-drop image to ComfyUI queue**
Any gallery image can be dragged to a "ComfyUI" drop target that sends it to the running ComfyUI instance's queue via the API.
- Pros: Most generally useful (not tied to stitching). Natural extension of drag-and-drop patterns.
- Cons: Drop target UX requires detecting a running ComfyUI instance.

**D — ComfyUI workflow editor integration**
Embed a workflow node graph editor (using the ComfyUI frontend's JSON format) within the app. Allow users to build post-processing workflows without opening a browser.
- Pros: Seamless integration.
- Cons: Massive scope. The ComfyUI frontend is a complex React app — embedding it is impractical without `QWebEngineView` (which is banned due to JVM conflicts). Skip.

**E — Workflow template library**
Ship a set of pre-built workflow templates (upscale, denoise, colorise, inpaint borders) that users can select from a dropdown. Auto-configure the template with the correct input image.
- Pros: Low barrier to entry for non-ComfyUI-expert users.
- Cons: Templates must be kept up to date with ComfyUI node changes.

**Recommendation:** C is the most generally useful (not tied to stitching). A as a stitching-specific QoL improvement. E to lower the barrier for first-time users. Skip D.

---

## 4.9 Safetensors Metadata Viewer

**Pain point:** `safetensors_metadata.py` exists but is not exposed in the GUI. Users managing LoRA and checkpoint files want to inspect metadata without external tools.

### Options

**A — "Inspect Model" button in LoRA/generate tabs [Quick Win]**
Load any `.safetensors` file and display its metadata in a read-only `QDialog` with a `QTreeWidget` (key-value tree for nested metadata).
- Metadata fields: training parameters, trigger words, base model, hash, file size, architecture.
- Pros: Quick-win improvement to existing tabs. Minimal new code.
- Cons: Narrow scope (only accessible from specific tabs).

**B — Drag-and-drop model inspector panel**
A dedicated side panel where users drag `.safetensors`, `.ckpt`, and `.pt` files to see their metadata, architecture summary, and estimated VRAM usage.
- VRAM estimation: based on parameter count × dtype size (e.g., float16 = 2 bytes/param).
- Pros: Discoverable from anywhere in the app. Useful for model management.
- Cons: Larger investment. Needs VRAM estimation logic.

**C — Model comparison view**
Select two model files and display their metadata side-by-side for comparison (e.g., two LoRA checkpoints from different training runs).
- Pros: Useful for evaluating training progress.
- Cons: Niche use case. Better as a follow-on to A or B.

**D — Model hash verification**
Display the sha256/blake3 hash of the model file alongside the embedded metadata hash (if present). Show a green/red indicator for integrity verification.
- Pros: Security and provenance benefit.
- Cons: Hashing large files takes a few seconds (3–5s for a 6 GB model). Should run asynchronously.

**Recommendation:** A is a Quick Win improvement to existing tabs. B is better UX but a larger investment. D adds security value with minimal extra effort on top of A.

---

## 4.10 REST API Layer for Remote Control

**Pain point:** The Django/Celery `api/` layer exists but its relationship to the desktop app's features is undocumented. Mobile clients (§5.6) and automation scripts need a well-defined API.

### Options

**A — OpenAPI 3.0 schema for existing endpoints**
Document all existing `api/urls.py` endpoints with `drf-spectacular` or `drf-yasg`. Generate a Swagger UI available at `/api/docs/`.
- Pros: Immediate discoverability for all consumers. Zero new endpoints.
- Cons: Requires annotating existing views.

**B — Trigger desktop operations via REST**
Expose long-running operations (stitch, scan, convert) as REST endpoints that enqueue Celery tasks. Return a job ID for status polling.
- Pros: Enables CLI automation and mobile remote control.
- Cons: Desktop app must be running with the Django server active.

**C — WebSocket real-time status**
Add a WebSocket endpoint (`/ws/jobs/{job_id}/`) that streams stage-level progress events as JSON. Pairs with §2.7 (progress and cancellation).
- Pros: Real-time progress in any WebSocket-capable client (browser, mobile, CLI).
- Cons: Django Channels dependency. Adds server infrastructure complexity.

**Recommendation:** A first (document what already exists). B as the automation-enabling extension. C for real-time mobile/web clients.

---

## 4.11 ASP Quality Feedback Interface (RLHF)

**Pain point:** The `StitchRewardModel` in `bench_anime_stitch.py` (§1.10A, S29) uses random weights until feedback is collected. There is no UI for users to rate stitching outputs so the reward model can learn meaningful preferences. Without rated outputs, the RLHF loop cannot close and the reward model never improves.

### Options

**A — Inline rating panel in StitchTab [Quick Win]**
After each stitch completes, show a 5-point rating widget (thumbs up / thumbs down / star rating) below the output preview. Ratings are written to a `~/.image-toolkit/stitch_feedback.jsonl` file as `{test_id, asp_score, simple_score, user_rating, timestamp}`. The reward model loads this file at startup to fine-tune weights.
- Implementation: ~80 LOC — `QToolBar` with `QSlider` (1–5 stars) + "Submit" button. Writes to JSONL via `json.dumps` + `f.write`.
- Pros: Minimal UI work. JSONL is portable and auditable.
- Cons: No per-seam granularity — only a global output rating.

**B — Side-by-side comparison mode with preference labelling**
Show ASP output and simple-stitch output side by side. User clicks "this one is better" (or "equal"). Preference pairs `(asp_result, simple_result, preferred)` are written to the feedback file.
- Pros: Generates richer comparative data (Bradley-Terry model compatible). Directly maps to RLHF preference learning.
- Cons: Requires the simple-stitch output to be retained alongside the ASP output. 2× disk usage per test.

**C — Batch rating mode for existing outputs [Quick Win]**
A separate "Rate Previous Outputs" dialog that loads already-saved PNG outputs from `~/.image-toolkit/stitched/` and presents them one-by-one for rating. Useful for rating the 96-test corpus in bulk.
- Pros: No blocking of the main stitch workflow. Can be done asynchronously.
- Cons: Must reconstruct metadata (which test, what parameters) from the output filename.

**D — Per-seam quality annotation**
After stitching, show each boundary seam zone as a thumbnail strip. User rates each seam 1–5. The reward model receives per-seam signals rather than a global output score — finer-grained training.
- Pros: More useful for targeted seam parameter tuning (feather width, gain, DP seam routing).
- Cons: 13 seams per output × ~30s per seam = ~7 minutes of annotation per dataset. Fatigue risk.

**Recommendation:** A immediately (simplest path to start collecting feedback). B for users who want to generate comparative DPO-style preference data. C as a bulk-annotation tool for the existing 96-test corpus. D as an advanced mode once A is validated.

---

## Anchor Index

| Section | Anchor |
|---------|--------|
| 4.1 Batch Stitching | [#41-batch-stitching](#41-batch-stitching) |
| 4.2 Scrolling Video Export | [#42-export-stitched-panorama-to-scrolling-video](#42-export-stitched-panorama-to-scrolling-video) |
| 4.3 CLIP Semantic Search | [#43-clip-based-semantic-image-search](#43-clip-based-semantic-image-search) |
| 4.4 Auto-Tagger | [#44-auto-tagger-integration](#44-auto-tagger-integration) |
| 4.5 Multi-Monitor Wallpaper | [#45-multi-monitor-wallpaper-support](#45-multi-monitor-wallpaper-support) |
| 4.6 Cross-Directory Dedup | [#46-image-deduplication-across-directories](#46-image-deduplication-across-directories) |
| 4.7 Slideshow Improvements | [#47-slideshow-improvements](#47-slideshow-improvements) |
| 4.8 ComfyUI Integration | [#48-comfyui-workflow-integration-for-post-processing](#48-comfyui-workflow-integration-for-post-processing) |
| 4.9 Safetensors Metadata Viewer | [#49-safetensors-metadata-viewer](#49-safetensors-metadata-viewer) |
| 4.10 REST API Layer | [#410-rest-api-layer-for-remote-control](#410-rest-api-layer-for-remote-control) |
| 4.11 RLHF Quality Feedback | [#411-asp-quality-feedback-interface-rlhf](#411-asp-quality-feedback-interface-rlhf) |
