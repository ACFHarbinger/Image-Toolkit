# Gate D review and #745

Reviewed Grok `ee3cc3d3` (#779), Mistral `c9b25820` (#780), and Kimi `2f104ae7` (#781) together on `review/dl-d-745`, based on main `55e9e785`. The integration preserves #778's recording, advisor and asynchronous report-card fixes.

## Corrections

- **Grok / #742:** thumbnails now survive filmstrip rebuilds; results carry a run generation so an old run cannot update a new run's buttons. Thumbnail threads exit when idle. Image dimensions are checked before decoding. Scrubbing maps to optimizer steps, not point indices. Epoch display translates zero-based events.
- **Mistral / #743:** zero deltas report rank zero. QR reduces the SVD to the low-rank core instead of materializing large dense weight matrices. PEFT alpha/rsLoRA scaling is applied when saved configuration is available.
- **Mistral / #748:** perturb normal sequence tensors and match device/dtype; seed VAE sampling and noise on the correct device; supply SDXL pooled embeddings/time IDs; reject empty evaluation data; load saved PEFT adapters instead of injecting into an unconfigured base model. The selected checkpoint is used, and the unchanged checkpoint is marked at alpha zero. Worker cleanup releases the GPU lease even if the dialog disappears. Unsupported adapter formats fail explicitly before a base-model load.
- **Kimi / #747:** resolve output directories when `lora_path` names a weights file. Require exact epoch-end sample steps, remove guessed epoch boundaries, and avoid comparing a grid against itself. Resume ratings by replaying surviving comparisons rather than retaining contributions from deleted checkpoints.
- **Pipeline integration:** remove obsolete logging kwargs from `_build_tuner`; they otherwise raise `TypeError` before training starts.

Correction commit: `010829a1`; draft integration: `fdb1d92c`.

## #745 implementation

Commit `60649f28` adds **Experiment from this run…** to the report card. Standard diffusion LoRA runs can vary learning rate, rank, batch size or epochs across 2–6 explicit values.

- Worker prepares a copied, hashed dataset with captions and preserved nested paths. The source's all-training/no-validation split, instance prompt, prompt suite and shared seed are recorded. Missing source datasets and unsupported engines are rejected.
- Remote base-model revisions are pinned once; local model files are hashed and checked before each child. Every child records its parent experiment ID and varied field/value and has separate outputs, events and process logs.
- Preview shows run count, estimated optimizer steps and dataset-copy storage. Launch is explicit; children run sequentially under one app GPU lease. Failure stops the queue; cancellation terminates and waits for the active process group. Each process exits before another model loads.
- Live small-multiple raw-loss plots share optimizer-step and loss axes. The UI explicitly distinguishes training loss from held-out quality and the source run from the newly seeded controls.
- Data/results persist under `~/Downloads/Data/Tests/dl-experiments/`. Manifests and per-run JSONL remain available after closing the dialog.

## Remaining limitations / merge guidance

- **#742/#747 are not end-to-end complete:** neither LoRATuner nor LoRATunerV2 calls `log_sample_grid` or `save_sample`. The new writer and consumers work with supplied grids, but ordinary training still produces none. Grok's claim that landing #779 automatically enables tournaments is therefore incorrect. Wire checkpoint sample production with fixed prompts/seeds before closing these issues; do not synthesize checkpoint identity from unrelated previews.
- Geometry supports recognized linear low-rank factors. LoHa/LoKr and convolutional factor reconstruction remain unsupported. Loss slices require a PEFT checkpoint with `adapter_config.json`; unsupported finals/formats are rejected rather than evaluated as an unadapted base model.
- #745 currently supports the standard LoRA engine, not GAN/LyCORIS. It preserves the source engine's all-training split; there is no new validation split or sample generation. Missing temporary source data must be restored. Previously completed experiments are persisted but have no dedicated history/reopen browser yet.
- No real GPU training, sampling or diffusion loss-slice evaluation was run. These drafts should retain that qualification; CPU/stub checks do not prove real model compatibility or VRAM sufficiency.

## Validation

130 distinct targeted tests passed: 71 backend and 59 GUI tests across the affected files. Checks cover snapshot isolation and nested captions, revision/parent identity, sequential failure/cancellation, step alignment, rank math, SDXL conditioning, thumbnail lifetime, tournament resume and report-card integration. Pipeline/config constructor contract, Ruff and `git diff --check` passed. No benchmark, full test suite or GPU workload was launched.
