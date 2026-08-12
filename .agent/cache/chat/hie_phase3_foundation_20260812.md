# HIE Phase 3 Foundation — Chat

Date: 2026-08-12

Project status synchronization: HIE issues #5/#6 and parent Track 01/02 cards are `In progress`; HIE issue #7 and parent Track 03 are `Ready`; issue #8/Track 04 remain `Backlog`.

Implementation slice:

- Added dependency-light `ModelSpec`, `ModelProposal`, `ModelAdapter`, and `ModelUnavailable` contracts.
- Added an optional `MattingAdapter` foundation without importing PyTorch/ONNX or committing weights.
- Added inspectable `PolicySpec`/`PolicyProposal` contracts and the Phase 1 `BrushAssistantPolicy` shell.
- Proposals are deterministic, previewable, and separate from document mutation; feedback is explicitly bounded.

Next review point: replace the matting/policy shells with optional backend adapters and connect their proposals to the shared pipeline contract after the model artifact/device policy is agreed.
