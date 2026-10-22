# S-01 gallery spike — go/no-go note

— Grok, 2026-10-22. Issue #887. Harbinger decides. This note is the measurement record, not the decision.

## What was measured

Stills are `backend.write_render_stills` (`backend/src/image/render_cache.cpp`). It writes a JPEG into the caller’s cache directory and returns the path, the kind, and the frame index. It does not return a pixel buffer. `max_edge` is clamped to 16..512. Video and GIF seek to `floor(frame_count / 2)` when the container reports a count of at least 2; otherwise they keep the first decodable frame and report index 0.

The webview helper `renderCacheAssetUrl` accepts only a path under `/.image-toolkit/cache/render/` with no `..`. That is the directory already allowed by `assetProtocol.scope` in `frontend/src-tauri/tauri.conf.json`. Other paths, including originals, become no `src`. `VirtualGallery` mounts only the visible window.

Animated preview is a separate `AbortSignal` / `threading.Event` request. Cancelling it writes nothing. This spike does not decode that request.

## Evidence

Targeted checks only. No full suite and no corpus benchmark.

- `pytest middleware/test/shell/test_render_cache.py`: 4 passed in 0.31s.
  - A 400×100 PPM written with `max_edge=64` produced a JPEG whose long edge is at most 64, inside the tmp cache, smaller than the source.
  - A 9-frame ffmpeg clip (`color=c=green:s=64x48:r=1`) reported `frame_index == 4` and a long edge of at most 32.
  - A missing file returned an empty cache path and an error.
  - A cancelled animated preview did not create the render directory.
- `vitest run src/shell/gallery/gallery.test.tsx`: 3 passed.
  - 100,000 items, viewport 600px, row 120px, 5 columns: **30 cells mounted** at the top of the list (`data-mounted=30`). A scroll of 48,000px stays at or under 40 mounted cells and does not reach the end.
  - One original path inside that window produced no `<img>`. The other 29 sources were the render-cache path.
  - That render took **25.39 ms** in jsdom, under the 1s bound in the test.
  - An already-aborted preview, and one aborted while pending, both reject with `AbortError`.

## Recommendation

**Go for gallery stills** on this path: C++ writes the bounded middle-frame JPEG into `~/.image-toolkit/cache/render/`, and the webview shows only `asset://` URLs for that directory. The 100k grid does not mount the corpus.

**Not part of that go:** animated playback. The cancellation boundary is in place, and the decoder is not. It stays a separate request and must not write the original into the still cache.

Follow-ups if the still path is accepted, not blockers for this spike:

- Share `load_image_batch`’s reduced JPEG decode instead of `cv::imread`.
- Containers that report no frame count still fall back to frame 0.
- `library.listings` is still the unported catalog placeholder from #870. Wire this grid there only after the go.

— Grok
