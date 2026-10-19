# HIE Phase 3 Policy/Model Sequence — Chat

Date: 2026-08-12

Implementation slice for Track 03 (DL/RL):

- Added the optional `SuperResolutionAdapter` contract with scale metadata and
  the same unavailable-backend behavior as matting.
- Added deterministic, preview-only policy shells for `GlobalTonePolicy` and
  `CropCompositionPolicy`, completing the planned Phase 1 sequence after the
  existing `BrushAssistantPolicy`.
- Added exports and tests; no PyTorch/ONNX dependency or model weights are
  required.

Validation: `middleware` pytest suite passes with 23 tests.

Project status reminder: Track 03 / HIE issue #7 is actively being implemented
and should be in the **In progress** tab. Track 01 (#5), Track 02 (#6), and
Track 04 (#8) remain respectively **In progress**, **In progress**, and
**Backlog** unless the project board is changed separately.

Next boundary: connect these proposals to the shared pipeline/orchestrator
contract once model artifact, device, and acceptance semantics are agreed.
