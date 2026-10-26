# 3. Hybrid document model and modifier graph

Date: 2026-08-20

## Status

Accepted

## Context

HIE Phase 1 ([issue #5](https://github.com/ACFHarbinger/Hybrid-Image-Editor/issues/5),
roadmap 01) needs a versioned document contract that both PySide6 (`gui/`)
and Tauri (`frontend/`) can share, without a still-image vs video fork.

## Decision

1. **Still images are one-frame sequences.** `FrameSequence` always has
   `len(frames) >= 1`. A photograph is `FrameSequence.still(path)`
   (`length == 1`, `fps == 0`). Video is the same type with N frames.
   Downstream APIs take a sequence; they do not special-case stills.

2. **Hybrid canvas: layer stack + optional modifier DAG.** Layers composite
   bottom-to-top (`opacity`, `blend_mode`, optional `masks`). Each layer
   may attach `Modifier` nodes. `ModifierEdge` edges form a DAG across
   those nodes. Cycles are a schema error.

3. **Python JSON is the host-facing schema.** `middleware/src/document.py`
   (`SCHEMA_VERSION = 1`) is the contract UIs serialize. Round-trip is
   canonical (`sort_keys`, stable separators); `snapshot_id()` is SHA-256
   of that JSON. `DocumentHistory` is snapshot-based undo/redo.

4. **C++ value types are the logic-core mirror, not a second JSON dialect.**
   `logic/include/document.hpp` (`kDocumentSchemaVersion = 2`) and
   `RenderGraph` (`render_graph.hpp`) own topological evaluation, dirty
   tiles, and cache invalidation. They are not a second on-disk format.

5. **Unsupported schema versions fail closed.** `Document.from_dict`
   raises `DocumentSchemaError` when `schema_version` is missing or not
   exactly `SCHEMA_VERSION`.

## Consequences

- Track 05 video trim/splice extends `Timeline` / `ClipSegment` on top of
  the same sequence contract; it does not replace `Document`.
- A new on-disk field is a schema bump in `document.py` plus tests in
  `middleware/test/test_document.py`. C++ struct changes bump
  `kDocumentSchemaVersion` independently.
- PySide6 and Tauri both consume the Python JSON contract via middleware
  IPC; neither host owns a private document class.
