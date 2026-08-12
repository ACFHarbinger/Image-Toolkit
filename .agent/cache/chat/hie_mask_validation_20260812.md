# HIE mask validation — 2026-08-12

Added a shared `validate_inpainting_mask` helper to the CPU restoration
boundary and CLI. It rejects empty masks, full-image masks, and masks wider
than the configurable safety limit (50% by default). The CLI exposes
`--max-mask-coverage`; CPU runners apply the same check and record accepted
coverage in their job metadata. Updated Phase 3.10 and the changelog.
