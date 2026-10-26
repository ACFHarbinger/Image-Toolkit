# Roadmap 05: Video Editing Extension (design/scope note)

> **Status:** Design note only — no implementation yet.
> **GitHub:** unfiled — post-review, file HIE issue(s) + parent Image-Toolkit issue under this doc.
> **Requested by:** Harbinger, 2026-08-18 bus. Scope: trim start/end, remove inner ranges, splice multiple clips, further trim/remove/splice the result — the "runtime editing tab" mechanical primitive. **Not** SAM-2 tracking or keyframe propagation (this roadmap's other Phase 5 capabilities) — those are unrelated ML features, out of scope here.

## Why this doc exists

Phase 5 in `ROADMAP.md` names three capabilities (temporal keyframe propagation, SAM-2 tracking, video clip export) with no UX/data-model detail. This note specifies the trim/remove-range/splice slice only — a simpler, mechanical precursor to the ML-assisted parts of Phase 5, per the original request's own framing.

## What already exists (read before implementing — do not rebuild any of this)

**HIE side:**
- `middleware/src/document.py`: `Frame(source, duration_ms, metadata)` and `FrameSequence(frames: tuple[Frame,...], fps)`, with `FrameSequence.still(source)` for the single-image case today. Docstring is explicit: *"The model deliberately treats a still image as a one-frame sequence. UIs can therefore share document and undo/redo code when multi-frame editing arrives."* — this is the intended landing spot; extend it, don't add a parallel timeline type.
- `middleware/src/document.py`: `DocumentHistory` (`commit()`/`undo()`/`redo()`) — reuse for timeline undo/redo.
- `middleware/src/pipeline/session.py`: `PipelineSession` — what `hie_tab.py` already owns and wires to the sidebar.
- `middleware/src/jobs/` (`JobHandle`, `restoration.py`, `cpu_restoration.py`) — the cancellable-job pattern already used for long-running restoration work; an ffmpeg export is the same shape of work.
- `logic/include/document.hpp`'s C++ `MediaAsset`/`Frame`/`FrameSequence` are a schema placeholder only — no frame extraction, video I/O, or temporal logic implemented anywhere in `logic/`. Nothing to build on there beyond the schema shape.
- HIE has exactly one GUI tab today (`gui/src/hie_tab.py`, flat `QWidget`, no tab-base class, no `gui/src/tabs/` package). A video editing tab establishes that package for the first time in HIE — follow ASP's `gui/src/tabs/` convention (`submodules/ASP/gui/src/tabs/`) as the closest precedent in this codebase, not a HIE-specific pattern (there isn't one yet).

**Main-repo side (`gui/src/`, NOT HIE) — the real reuse target:**
- `gui/src/helpers/video/video_extractor_worker.py` (`VideoExtractionWorker`) and `gui/src/helpers/video/gif_extractor_worker.py` (`GifCreationWorker`) already implement start/end trim + inner-range removal for **one source clip**: `cuts_ms: list[(start_ms, end_ms)]` → `_get_keep_regions()` inverts/merges cuts into keep-segments → ffmpeg `select`/`aselect` filter or MoviePy `concatenate_videoclips` over the kept subclips.
- `gui/src/tabs/core/extractor_tab/_cuts_logic.py` (`_CutsLogicMixin`) is the existing UI pattern for editing a `cuts_ms` list (add/edit/delete cut, context menu, chip display) — reuse the *interaction pattern*, not the code (it's extractor_tab-specific), for the new timeline widget.
- `gui/src/helpers/video/storyboard.py` (`StoryboardBuilder`) generates a sharded sprite-sheet scrub-preview per clip via one `ffmpeg -vf fps=...,scale=...` pass — the established fast-scrubbing pattern; reuse for timeline preview instead of decoding on every scrub.
- `gui/src/components/dialogs/frame_selection_dialog.py` does async single-frame extraction on a `QThread` for scrub preview.
- `gui/src/helpers/video/video_thumbnailer.py::media_backend_spawn_guard()` — **every** ffmpeg/ffprobe fork in this repo wraps in this guard (issue #81 crash family: concurrent ffmpeg fork racing the first `QMediaPlayer` construction). Non-negotiable for any new ffmpeg call site; `gui/test/core/test_ffmpeg_spawn_guard.py` pins the convention.

**The one genuine gap:** nothing in the repo splices *multiple source files* today. `concatenate_videoclips`/ffmpeg `concat` is only ever used to stitch the keep-regions of a *single* source clip back together after cut removal. "Splice multiple clips, then trim/remove/splice the result" has no existing counterpart.

## Data model: one primitive, not three

Trim, remove-inner-range, and splice are the same operation once you see a clip as an **ordered list of source-range references**, not three separate mechanisms:

```
ClipSegment = (source_path: str, in_ms: int, out_ms: int)
Timeline    = list[ClipSegment]   # ordered; a segment's source_path can differ from its neighbors
```

- **Trim start/end** = adjust `in_ms`/`out_ms` on the first/last segment.
- **Remove an inner range** = split one segment into two (`[in_ms, cut_start]` + `[cut_end, out_ms]`), dropping the removed middle. No separate "cut list" data structure needed — it's a list edit.
- **Splice** = insert another `ClipSegment` (any `source_path`) at a position in the list.
- **Further trim/remove/splice the result** falls out for free — the "result" is still just a `Timeline`, so every operation above still applies.

This generalizes `document.py`'s existing `Frame(source, duration_ms, metadata)` from a single still frame to a time-range reference, matching the file's own stated intent rather than adding a parallel type. A `Timeline` commits to `DocumentHistory` after each edit, for undo/redo — no new undo/redo mechanism.

**Non-destructive by construction:** a `Timeline` is pure metadata (paths + millisecond ranges); no media bytes are touched while editing. Export is the single, explicit, destructive step that renders one output file. Source files are never modified, at any point.

## Where cutting/rendering happens

- **Preview (scrubbing):** per-source `StoryboardBuilder` sprite sheets (already built, already fast), with the UI mapping global timeline-ms → `(segment index, local ms)` → the right sheet tile. No re-encoding for preview, ever.
- **Export (the one destructive step):** new module in the **main repo**, next to the existing workers — e.g. `gui/src/helpers/video/clip_splicer.py` — generalizing `_get_keep_regions()` from "keep-regions of one source" to "ordered segments across N sources." Prefer ffmpeg's `concat` demuxer over per-segment `-ss/-to` trims when codec/resolution/fps match across all sources (no re-encode); fall back to a full re-encode via filtergraph `trim`+`concat` (or MoviePy, matching the existing dual-backend pattern in `video_extractor_worker.py`) when sources differ. Every ffmpeg fork wrapped in `media_backend_spawn_guard()`.
- **Why main repo, not HIE:** this is ffmpeg subprocess execution, the exact concept `gui/src/helpers/video/` already owns; HIE's job is the timeline document model + UI, not re-implementing a second ffmpeg execution boundary. Matches this project's stated layering rule — keep each layer to the concepts it owns.
- **Job wiring:** wrap the export call in HIE's existing `JobHandle`/`RestorationPipeline` cancellable-job pattern (`middleware/src/jobs/`), the same shape `hie_tab.py`'s restoration button already uses — not a new progress/cancel mechanism.

## New tab

- First `gui/src/tabs/` package in HIE (ASP-style), e.g. `tabs/video_editor_tab.py`: timeline widget (segment chips, drag to reorder/trim — same interaction shape as `_cuts_logic.py`'s chips, reimplemented for HIE since that code is extractor_tab-specific), a scrub viewport (extend `HieViewport` or reuse `frame_selection_dialog.py`'s async-extraction pattern), an Export action wired to `clip_splicer.py` via a `JobHandle`.

## Open question for the implementer (not decided by this note)

Should timeline edits go through HIE's `ProposalPipeline`/`PipelineSession` (preview/accept semantics, built for ML policies) or talk to `DocumentHistory` directly? Trim/remove/splice are deterministic list edits, not ML proposals needing a preview-then-accept step — direct `DocumentHistory` use seems like the better fit and avoids forcing a deterministic operation through machinery built for policy proposals, but this is a judgment call for whoever implements it (or Harbinger), not settled here.

## Explicitly out of scope for this slice

- SAM-2 tracking, temporal keyframe propagation (Phase 5's other two items) — separate ML features, separate design pass.
- Exact widget layout/keyboard shortcuts — implementation detail.
