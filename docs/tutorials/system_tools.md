# System Tools — Tab Tutorials

The **System Tools** category groups the local file-manipulation tabs: converting media between formats, compositing images, finding duplicates, extracting frames, and driving your desktop wallpaper.

---

## Convert

Converts images and videos between formats. The tab has three subtabs — **Format**, **Codec**, and **Sampler** — each aimed at a different kind of conversion.

### Format subtab

Batch-converts image files from one *container format* to another (PNG → JPEG, WebP → PNG, …). Pick a source directory, select the images in the gallery, choose the output format, and run.

#### Aspect Ratio

Off by default; enable it with the **Change Aspect Ratio** checkbox to also reshape every converted image to a target aspect ratio. Two controls matter:

- **Mode** — what to do when the source image doesn't already match the target ratio:
    - **Crop** — cuts away the excess. No distortion, but pixels outside the target ratio are lost.
    - **Pad** — adds background bars (letterbox/pillarbox). Nothing is lost, but bars are added.
    - **Stretch** — resizes non-uniformly to fit. Nothing is lost and no bars appear, but the image is distorted.
- **Ratio** — the target ratio itself: presets `16:9`, `4:3`, `1:1`, `9:16`, `3:2`, or **Custom**, which reveals **W**/**H** spinboxes so you can type any ratio (e.g. 21:9 → W=21, H=9). The numbers describe a *proportion*, not a pixel size.

### Codec subtab

Re-encodes video files' internal streams without necessarily changing the container. Sources are scanned and can be filtered by their probed codec via toggle buttons.

- **Target Video Codec** — the codec the video stream is re-encoded to:
    - **Keep Original (No Re-encode)** — stream-copies the video untouched (fast, lossless); useful when you only want to re-encode the audio.
    - **H.264** — the universal compatibility choice; plays everywhere, larger files than newer codecs.
    - **H.265 / HEVC** — roughly half the size of H.264 at the same quality; slower to encode, needs a reasonably modern player.
    - **AV1** — best compression of the list and royalty-free; slowest to encode.
    - **VP9** — the WebM-ecosystem codec; good compression, well supported in browsers.
- **Target Audio Codec** — same idea for the audio stream: **Keep Original**, **AAC** (universal lossy default), **Opus** (best quality-per-bitrate lossy), **MP3** (legacy compatibility), **FLAC** (lossless, larger).
- **Quality (CRF)** — the Constant Rate Factor, 0–63. *Lower = higher quality and larger files.* The default 28 is a sensible size/quality balance for HEVC/AV1; try 18–23 for near-transparent quality. The value is automatically clamped to whatever range the selected target codec actually supports, so you never have to remember per-codec limits.
- **Speed** — the encoder's speed-vs-efficiency preset: **Fastest → Fast → Balanced → Slow → Best Quality**. Slower settings spend more CPU time searching for better compression: the *same* CRF produces a *smaller* file, but encoding takes longer. Quality is governed by CRF; Speed mostly trades encode time against file size.

### Sampler subtab

Resamples (rescales) images and videos. Scale either by a **factor** (with 0.25×/0.5×/2×/4× quick buttons) or to explicit **W×H dimensions** (optionally preserving aspect ratio).

- **Algorithm** — the resampling filter used for the rescale:
    - **Lanczos** — highest quality (sharpest, fewest artifacts), slowest. The default choice for quality work, especially downscaling.
    - **Bicubic** — good quality at moderate speed; a fine general-purpose middle ground.
    - **Bilinear** — fast with acceptable quality; slight softening.
    - **Nearest Neighbor** — copies the closest pixel with no interpolation: "pixel-perfect" but aliased. The *only* correct choice for pixel art or when you must not introduce new colors; wrong for photos.

---

## Merge

Composites multiple selected images into a single output. Select images in the gallery, pick a **Mode**, configure it, and press **Run Merge**.

### Merge Mode

- **canvas** — free-form compositing on an interactive canvas (see below). The output is exactly what you laid out.
- **horizontal** / **vertical** — concatenates the selected images in a row/column, with a configurable **Spacing (px)** gap and an **Alignment/Resize** rule (`Default (Top/Center)`, `Align Top/Left`, `Align Bottom/Right`, `Center`, `Scaled (Grow Smallest)`, `Squish (Shrink Largest)`) governing how differently-sized images line up.
- **grid** — arranges images into a **Rows × Cols** grid (contact-sheet style).
- **panorama** / **stitch** — content-aware stitching for overlapping shots. **Perfect Stitch Mode (Digital Art)** enables the anime-pan pipeline (template matching + pyramidal blending) with **Edge Crop** (neutralizes vignettes before matching) and **Pyramid Levels** (seam blend width), plus the *AI Optimization* toggles (Siamese order-agnostic matching, APAP parallax mesh, LSD structure preservation, AnimeGAN2 refinement, BiRefNet character-aware seams, BaSiC luma correction, LoFTR dense matching, ECC sub-pixel alignment) and a **renderer** choice — `blend` (multi-band, robust), `median` (temporal denoise, sharpest), `first` (no blending, fastest).
- **sequential** — merges images in selection order rather than layout order.
- **gif** — assembles the selection into an animated GIF; a **Duration (ms/frame)** spinbox appears to set per-frame timing.

### The Merge Canvas (canvas mode)

Canvas mode turns the tab into a small layout editor:

- **Canvas size & background** — the header row sets the output pixel size (**W**/**H**, up to 20000×20000) and the **BG** fill for uncovered areas: `Transparent`, `White`, or `Black`.
- **Placing images** — clicking a gallery thumbnail toggles it onto/off the canvas. Each placed image is a movable, resizable tile: drag to move, drag its corner handles to resize.
- **Precise geometry** — selecting a tile activates the **X / Y / W / H** spinboxes below the canvas, letting you type exact positions/sizes (negative X/Y are allowed — tiles may extend past the canvas edge; anything outside is cropped in the output).
- **Join (snapping)** — right-click a tile to open the *Join* menu: **Join Top / Bottom / Left / Right** each list the other tiles; choosing one snaps that tile flush against the clicked tile's side with a 0-px gap (hovering a menu entry highlights the tile it refers to). This is the quick way to build exact strips or mosaics without pixel-nudging.
- Right-clicking empty canvas offers **Fit Canvas** (re-fit the view); **Remove Selected** and **Clear Canvas** manage placed tiles.

When you run the merge, the composite is rendered at the configured canvas size with each tile at its exact position and scale.

---

## Similarity

Finds duplicate or visually similar images inside a directory (optionally recursive), groups them, and helps you triage which copies to keep, hardlink, or delete.

### Scan Method

Ordered roughly from fastest/strictest to slowest/most tolerant:

- **Similarity Engine (tiered clusters)** — the recommended default. Runs the C++ multi-tier engine: exact hash → perceptual hashes → VP-tree/HNSW candidate search → structural verification, producing ranked clusters with cached results, so re-scans of the same directory are fast.
- **All Files (List Directory Contents)** — no similarity analysis at all; just lists everything so you can eyeball/manage the directory manually.
- **Exact Match (Same File — Fastest)** — byte-identical duplicates only (content hash). Catches copies and renames, nothing else.
- **Similar: Perceptual Hash (Resized/Color Edits — Fast)** — pHash-style fingerprints; catches resized, recompressed, or mildly color-edited variants. Misses crops and rotations.
- **Similar: ORB Feature Matching (Cropped/Rotated — Medium)** — local feature matching; robust to cropping, rotation, and moderate edits at moderate cost.
- **Similar: SIFT Feature Matching (Robust — Slow)** — stronger features than ORB; better recall on heavily transformed variants, noticeably slower.
- **Similar: SSIM (High Quality — Slowest)** — full structural similarity comparison; the most precise visual comparison and by far the most expensive — best on small, pre-filtered sets.

Use **Reset / Show All** after a scan to restore the full directory view (a scan filters the gallery down to the matched groups).

---

## Extractor

Extracts frames from media. Two subtabs: **Video** (frames/clips/GIFs out of video files) and **Image** (splitting one multi-frame image into its frames).

### Video subtab

Point **Source Directory** at a folder of videos/GIFs, click a thumbnail to open it in the built-in player (or an external one), then use the **Extraction Settings** section to produce output into the **Output Directory**.

#### Extraction Settings section

- **Recent Extractions / Load Config** — a history of your last extraction runs; selecting one and clicking *Load Config* restores that run's full parameter set (source, ranges, cuts, tags…).
- **Output Size** — resolution of extracted frames/clips: `Native` (source resolution), `Player` (whatever the player is currently sized to), or fixed presets `480p`–`4K`. **Vertical Output** swaps width/height for portrait sources.
- **GIF FPS** — frame rate used when exporting a range as GIF (1–60).
- **Mute Audio in MP4/GIF** — strips the audio track from clip exports.
- **Engine** — `FFmpeg` (fast, robust, recommended) or `MoviePy` (Python fallback).
- **Extraction Speed** — speed multiplier applied to exported clips (0.25×–4×), independent of the player's playback speed.
- **📸 Snapshot Frame** — saves the single frame at the current playhead position.
- **Set Start / Set End (+ Go)** — mark the in/out points of the extraction range at the current playhead; *Go* jumps back to a marked point. **🎞️ Extract Range** exports every frame in the range as images, **MP4 Extract as Video** / **GIF Extract as GIF** export it as a clip.
- **Cuts row** — *Set Cut Start* / *Set Cut End* / *Add Cut* define **sub-ranges to skip**: when the range is extracted, the listed cuts are removed from it (e.g. cut out an ad or a scene transition mid-range). *Clear Cuts* resets the list.
- **Frame Interval** — extract every Nth frame instead of every frame (e.g. `12 frames` keeps 1 in 12).
- **Smart Extract (FFmpeg)** — replaces the fixed interval with an FFmpeg filter that selects frames by content: `mpdecimate (De-duplicate)` drops consecutive near-identical frames (ideal for anime/limited animation); the `scene (0.1–0.6)` options keep only scene-change frames, with the number as the change threshold (lower = more sensitive = more frames kept).
- **Tags row** — attach named markers to timestamps; tags travel with the extraction history so you can annotate why a range mattered.
- If the **extraction queue** is enabled in Settings, configured extractions can be queued and processed later, sequentially or in parallel.

### Image subtab

Splits one image file that *contains* multiple frames — a vertical strip, horizontal strip, or grid sheet — into individual frame images.

#### Frame Layout section

- **Arrangement** — how frames are packed in the file: **Vertical** (stacked top-to-bottom), **Horizontal** (side by side), or **Grid** (rows × columns).
- **Frame Width / Frame Height** — the size of *one* frame in pixels. Strips only need one number (a vertical strip needs **Frame Height**; the width spans the whole image — and vice versa for horizontal). **Grid** needs both.
- **Offset X / Offset Y** — skips margin pixels before the first frame starts (for sheets with a border).
- **Spacing** — the pixel gap *between* consecutive frames (applied on both axes in Grid mode), for sheets with gutters.
- **Include partial last frame** — when the image size isn't an exact multiple of the frame size, the trailing remainder is normally shown dashed and skipped; check this to extract it too (as a smaller final frame).

The info label on the canvas toolbar always shows the source size and how many frames the current parameters produce, and the **Cut N Frames** button reflects the count live.

#### Frame Boundary Preview section

The canvas exists so you can *verify the boundaries before cutting*:

- Every frame that will be extracted is outlined in alternating **cyan/magenta** (alternating colors make the shared edge between adjacent frames readable). Any region the parameters leave uncovered is outlined **dashed amber** — if you see amber where a frame should be, your frame size or offset is slightly off.
- **Buttons** — **Fit** zooms out so the whole image is visible (overview); **1:1** shows exactly one image pixel per screen pixel; **＋ / －** step the zoom in/out.
- **Mouse** — the wheel zooms (anchored under the cursor, covering a huge 0.01×–80× range in a few notches), left-drag pans, and **double-click toggles** between fit-to-view and 1:1 at the clicked point.
- The intended verification loop: *Fit* for the overview → double-click a boundary to jump to pixel scale (rendering switches to hard, nearest-neighbor pixels at ≥100% so you can judge the edge to ±1 px) → adjust Frame Layout numbers if needed (the overlay updates live) → double-click back out → check the next boundary → **Cut Frames**.

Frames are saved as `{name}_f001.png`, `{name}_f002.png`, … into the configured output directory.

---

## Wallpaper

Controls your desktop wallpaper(s). Two subtabs: **System Display(s)** applies wallpapers to the real desktop; **Monitor Display** builds graph-driven wallpaper sequences per monitor.

### System Display(s) subtab

Shows your physical monitor layout; assign an image to each monitor from the scanned gallery, then apply.

#### Background Type

Each type reveals its own configuration controls:

- **Image** — a static wallpaper per monitor.
    - **Image Style** — how the image maps onto the screen. The list adapts to your desktop environment: on KDE — `Scaled, Keep Proportions`, `Scaled and Cropped (Zoom)`, `Centered`, `Stretch`, `Tiled`, `Center Tiled`, `Span`; on GNOME — `Wallpaper`, `Centered`, `Scaled`, `Stretched`, `Zoom`, `Spanned`, `None`; on Windows — `Fill`, `Fit`, `Stretch`, `Center`, `Tile`.
- **Slideshow** — cycles images automatically. Adds:
    - **Interval** (`min` + `sec`) — time between wallpaper changes.
    - **Order** — `Sequential`, `Reverse Sequential`, or `Random`.
    - **Start/Stop Background Daemon** — runs the slideshow as a detached background process that keeps cycling after the app closes (with **View Daemon Logs** for troubleshooting). A countdown label shows time to the next change. **Fetch Current Wallpapers** pulls what's currently on screen into the layout; **Skip Current Wallpapers** advances immediately.
    - **Image Style** — same as Image mode.
- **Smart Video** — a video file as an animated wallpaper.
    - **Video Style** — `Stretch`, `Keep Proportions`, or `Scaled and Cropped` (replaces Image Style while a video type is active).
- **Smart Video Slideshow** — cycles through *videos*; combines the Slideshow controls (Interval, Order, daemon) with the **Video Style** setting.
- **Solid Color** — no image at all. The gallery and scan directory are disabled; a **Color** swatch + **Select Color…** picker choose the flat background color.

### Monitor Display subtab

A per-monitor **wallpaper sequencer**: instead of a flat playlist, each display gets a *graph* whose traversal defines the wallpaper order.

#### Graph Canvas

- **➕ Add Node** — adds a wallpaper file as a node (you can also drag images from the gallery straight onto the canvas).
- **↩ Self-Edge** — the selected node repeats (loops on itself).
- **→ Connect** — draws an edge from the selected node to another; edges define what plays next.
- **🗑 Delete** — removes the selected node or edge (the `Del` key works too).
- **⊡ Fit View** — re-frames the whole graph.
- **★ Set Start** — marks the selected node as the traversal's entry point.
- **🗑 Clear Graph** — wipes the graph.
- The bottom bar operates on the traversal: **⇥ Export to Queue** appends the graph's current sequence to the monitor's Wallpaper Queue; **▶ Preview Timelapse** renders a quick preview video of the sequence; **▶ Start In-App Slideshow** cycles the queue while the app is open; **⏱ Start Slideshow Daemon** cycles it from a detached process that survives closing the app (one display's daemon at a time). The `-- / --` counter and `Timer` label show the live queue position and time to the next change; a summary line spells out the resolved sequence.

#### Node Properties

Double-click (or right-click) a node to edit it:

- **Display Mode** — how long the node's wallpaper stays up: **Fixed duration** (uses the **Duration (s)** spinbox, 0.5 s–24 h) or **Full video runtime** (video nodes hold until the video finishes).
- **Outgoing Edges** — the node's exits, listed in priority order: *playback always follows the topmost edge first*; drag entries to reorder, right-click to remove. Add a new edge by picking a target node, a **×N repeat count** (the target plays N times back-to-back when this edge is taken), and **+ Add Edge**.
- **Apply** commits the changes.

#### End of Graph Behavior

What happens when traversal reaches a node with no outgoing edges:

- **Repeat Graph** — start over from the start node.
- **Solid Color** — switch to a flat color (a **Pick Color** button + swatch appear).
- **Stay on Last Wallpaper** — freeze on the final wallpaper.
- **Return to First Wallpaper** — show the start node's wallpaper and stop.
- **Jump to Specific Wallpaper** — a node picker appears; traversal jumps there (letting you build an "intro once, then loop this part" structure).
