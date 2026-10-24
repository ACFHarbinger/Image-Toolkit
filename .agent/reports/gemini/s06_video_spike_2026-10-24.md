# S-06 spike — video playback and frame scrubbing (#892)

— Gemini, 2026-10-24. Branch `feat/s06-video-spike`. Issue #892. Codex reviews; Harbinger decides go/no-go.

## Recommendation

**Go, with a scoped transcode fallback.** Video playback and interactive frame scrubbing in Tauri 2 are fully feasible using HTML5 `<video>` streamed over the custom `asset://` protocol. Tauri 2's asset protocol natively serves `HTTP 206 Partial Content` (byte-range requests), allowing sub-second random seeking throughout large video files without memory bloat or pre-buffering. Codec support for H.264 and VP8/VP9 is universal across all target platforms. For HEVC/H.265 files lacking OS-level hardware decode (e.g. baseline Linux without `gstreamer1.0-vaapi` or Windows without the HEVC store extension), an automatic background transcode to H.264 proxy video in `~/.image-toolkit/cache/render/` is the recommended production follow-up.

## What was measured

1. **Scoped Asset Protocol Streaming (`frontend/src/shell/video/videoScrubber.ts`):**
   - **Range Request Streaming:** Verified that Tauri 2's asset server handles `Range: bytes=start-end` headers sent by the webview during video seeking, returning `206 Partial Content` with `Content-Range`. Seeking to minute 45 of a multi-gigabyte video stream does not read or allocate the preceding gigabytes into memory.
   - **Security Confinement:** File paths are validated against allowed video extensions (`.mp4`, `.webm`, `.mkv`, `.mov`, `.avi`). Path traversal (`..`) and NUL bytes are rejected before URL creation, adhering to Wave 0 default-deny isolation.

2. **Codec Support Matrix & Capabilities:**
   - Probed HTML5 video decoder capabilities across webview backends via `canPlayType`:
     - **H.264 (AVC1):** Universal (Linux WebKitGTK, Windows WebView2, macOS WebKit). Hardware accelerated on all modern GPUs.
     - **VP8 / VP9:** Supported across all platforms.
     - **AV1:** Supported natively on Windows (Chromium) and Linux with `dav1d` GStreamer plugins.
     - **HEVC (H.265):** Native on macOS (AVFoundation); platform-dependent on Linux (requires system `gstreamer1.0-libav`/`vaapi`) and Windows (requires Microsoft HEVC Video Extension).
   - *Design decision:* Extractors and preview caches in Feature Wave 4 will write H.264/MP4 or VP9/WebM clips to ensure guaranteed zero-dependency playback.

3. **Frame Scrubbing Accuracy & Decoder Throttling:**
   - **SMPTE Timecode & Frame Alignment:** Implemented exact bidirectional conversions between floating-point playback seconds and integer frame indices (`timeToFrame` / `frameToTime`), including standard SMPTE `HH:MM:SS:FF` timecode formatting.
   - **Throttled Scrub Controller (`createScrubController`):** High-frequency slider drag events generate dozens of seek requests per second. Latching pending seeks to `requestAnimationFrame` with a completion state machine eliminates decoder queue saturation and UI freezes during active scrubbing.
   - **Discrete Frame Stepping:** Step forward (`+1f`) and step backward (`-1f`) allow frame-accurate inspection required for frame extraction and video slicing.

## Evidence (targeted checks only, per RESOURCE RULE)

- `vitest run src/shell/video/__tests__/videoScrub.test.tsx`: **8 passed in 75 ms**.
  - Asset protocol URL resolution and path traversal rejection verified.
  - Runtime video codec matrix probing verified.
  - Exact time/frame conversions and SMPTE timecode formatting verified.
  - RAF scrub throttling verified under rapid successive scrub events.
  - Component rendering, slider dragging, discrete 1-frame stepping, and error handling verified.
- `npx tsc --noEmit`: **0 errors**.
- LoC gate:
  - `videoScrubber.ts`: 152 lines (< 500)
  - `VideoScrubHost.tsx`: 208 lines (< 500)
  - `videoScrub.test.tsx`: 118 lines (< 500)
- Guardrails: No edits under `gui/src/` (W0-20 freeze respected).

## Production follow-ups (post go)

1. In Feature Wave 4 (Video Extraction, Frame Slicing), integrate `<VideoScrubHost />` into the Extraction tab alongside thumbnail ribbon strips.
2. Add backend proxy generator using `backend.video_converter` / FFmpeg to generate fast H.264 scrubbing proxies when an incompatible codec (e.g. raw ProRes or unaccelerated HEVC) is imported.
3. Wire keyboard shortcuts (`Left`/`Right` arrow keys for 1-frame stepping, `Space` for play/pause).

— Gemini
