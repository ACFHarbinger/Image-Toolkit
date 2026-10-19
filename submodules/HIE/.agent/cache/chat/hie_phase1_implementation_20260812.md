# HIE Phase 1 Implementation — Chat

Date: 2026-08-12

## Coordination

Resuming from Gemini's architecture proposal and the confirmed hybrid-stack/multi-modal decisions. The first implementation slice targets GitHub issue #5: a versioned, deterministic Python document contract plus the matching C++ value-model header.

## Scope for this pass

- One-frame stills use the same `FrameSequence` API as multi-frame media.
- Layers retain source identity, opacity/blend state, masks, and ordered modifier nodes.
- Modifier edges are validated as a DAG; duplicate IDs, missing references, cycles, and unsupported schema versions fail clearly.
- JSON serialization is canonical (`sort_keys`, stable separators) so snapshots can support undo/redo and reproducible cache keys.
- Tests cover still/multi-frame construction, deterministic round-trips, validation failures, and snapshot history.

## Follow-up

The next agent should review the contract against the eventual central `base` binding and extend the C++ implementation once the shared Image-Toolkit binding boundary is available.
