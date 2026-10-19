# HIE Foundation Coordination — Chat

Date: 2026-08-12

## Completed in this pass

- Corrected C++ build and documentation references to `logic/include/`, `logic/src/`, `logic/test/`, and `logic/benchmark/`.
- Renamed starter C++ targets and namespace to `hybrid_image_editor`.
- Added initial `middleware/` Python contracts and test, a TypeScript frontend shell, and a PySide6 GUI shell.
- Replaced inherited template branding and identifiers across documentation, agent guidance, workflows, and infrastructure defaults; Helm chart directory is now `infra/global/helm/hybrid-image-editor/`.

## Gemini coordination note

Gemini CLI was unavailable for substantive review because its account reported no remaining credits. The existing Gemini proposal in `cache/gemini/` remains the working brainstorm input. Chat's synthesis is therefore provisional and should be validated by the product lead and later agents.

## Provisional architecture decisions to discuss

1. Use a non-destructive document model: immutable source assets plus an ordered operation graph/layer stack, with deterministic snapshots for undo, export, and reproducibility.
2. Treat an image as a one-frame media sequence internally where practical, but keep frame scheduling and temporal caches as optional capabilities until video work begins.
3. Keep C++ responsible for deterministic pixel/matrix/optimization kernels; keep Python responsible for orchestration, model lifecycle, experiment configuration, and policy logic.
4. Define one versioned middleware command/progress/result contract consumed by both UIs; embedding and standalone launchers should differ only in transport/bootstrap.
5. Start ML assistance as explicit, cancellable proposals that users can inspect and accept, rather than opaque automatic mutations. Log model/version/config metadata with every accepted operation.

## Questions for the product lead

See the final response for the joint brainstorming questions. No roadmaps or GitHub issues should be created until those answers and the proposed roadmaps are verified.
