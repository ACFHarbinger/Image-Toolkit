# Kimi sample-production follow-up

Reviewed `15467d2a` from PR #781 and integrated it into `review/dl-d-745` / PR #782 as `864b7309`, preserving the prior review corrections.

Fixed findings:

- **SDXL sampling always failed:** `StableDiffusionXLPipeline` does not accept `requires_safety_checker`. Removed that argument from the XL branch; a regression binds the call against the installed diffusers constructor signature rather than a permissive mock.
- **Shared training state leaked:** exceptions bypassed UNet mode restoration, while text encoders retained their training modes during sampling. Sampling now temporarily evaluates all shared modules and restores every module's mode, tensor dtype and Python/NumPy/Torch RNG state, including failure paths. No model-weight clones are needed.
- **Avoidable VRAM pressure:** four prompts previously sampled in one batch while training weights/optimizer remained resident. Sampling now processes one prompt at a time and uses a generator on the pipeline device. V2 drops the pipeline reference before emptying the allocator cache.
- **Configuration was ineffective:** `sample_grids` and `validation_seed` were not forwarded by the Hydra pipeline. Both are wired through; base config declares the opt-out and defaults validation seed to the run seed. A real Hydra composition test verifies `training.sample_grids=false` and seed propagation.
- **Final sample metadata/work:** V2 now uses the actual final epoch rather than the planned epoch budget, and does not regenerate the last checkpoint grid at the same step. Only the main process writes diagnostic grids.
- **Experiment integration:** V1 accepts an explicit sample prompt suite/seed and opt-out; #745 passes its frozen prompt suite/seed and mentions final sampling in the cost preview.

Validation: 74 targeted tests passed (47 backend, 27 GUI), including installed-signature checking, state restoration on failure, serial sampling, Hydra configuration, checkpoint deduplication, and experiment/GUI regressions. Ruff and diff checks passed. No model download, GPU workload, benchmark or full suite was launched.

The missing-call-site blocker is addressed in the combined branch. V1 still has only a final artifact/grid, so one V1 run cannot supply a checkpoint tournament. Actual diffusion sampling and VRAM sufficiency remain unverified, including LyCORIS/other model configurations; keep PR #782 draft pending that validation. This report supersedes the missing-producer finding in the earlier Gate D report, not its other format/support limits.
