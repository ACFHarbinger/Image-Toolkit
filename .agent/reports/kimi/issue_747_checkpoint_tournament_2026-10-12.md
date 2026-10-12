# #747 — Checkpoint tournament: blind ELO-ranked pairwise comparison

Date: 2026-10-12 · Author: Kimi · PR: (this branch) · Branch: `dl-d-747-checkpoint-tournament` off `main`

## What shipped

**Pure core** — `backend/src/core/checkpoint_tournament.py` (torch-free, Qt-free):

- Classic ELO (start 1500, K=32, ties 0.5) with repeat-pair refusal; Glicko-lite
  uncertainty (±2·RD, RD = 350/√(games+1)); standings flag "provisional until
  ~10+ comparisons" per the issue.
- Swiss-ish pairing: closest ratings first, fewest-combined-games tiebreak,
  seeded-rng deterministic for tests; `avoid` set for session skips.
- Persistence to `<run_dir>/tournament.json` (`{version, run_id, entries,
  history, promoted}`) — resumable across sittings; `attach_state` rebinds
  saved ratings to freshly discovered checkpoints, prunes history/promotion
  for deleted checkpoints.
- Discovery (read-only): checkpoints from `record.json → config.output_dir →
  checkpoint-epochNNNN/` (diffusers dirs with weights) + final artifact;
  sample grids from `<run_dir>/samples/step-*.png` (Gate D.2 writer layout,
  consumed as a contract — no dependency on #779's code). Grid ↔ checkpoint:
  latest grid at or before the epoch's max step from `events.jsonl`, even-split
  fallback when events lack epoch tags.

**GUI** — `gui/src/components/dialogs/checkpoint_tournament_dialog.py`:

- Embedded `ImageCompareWindow` restricted to side-by-side (synced pan/zoom
  reused, no new canvas): pane badges forced to "A"/"B", overlay/diff buttons
  and sub-bar hidden, mode-switch keys swallowed — ids blind, ties allowed.
- Vote bar (← A / Tie / B → / Skip) + window shortcuts; live standings table
  (ELO ± margin, games, W–T); sitting ends after 12 comparisons (fatigue cap);
  "Promote Winner…" writes provenance into `tournament.json` and emits a
  `PinnedRun` (`lora_path` → weights file inside the checkpoint dir) that the
  train tab forwards to the workspace spine via duck-typed `note_run`.
- Entry point: "Start Tournament…" on #746's report card, shown only when the
  run actually has ≥2 checkpoints and ≥2 grids.

## Verification

- 33 backend + 16 GUI new tests (ELO math vs hand-computed values, pairing
  exhaustiveness/determinism, JSON round-trip, resume pruning, discovery edge
  cases incl. a directory named `*.safetensors`, blind headers, vote/skip/cap/
  resume/promote flows, report-card button gating).
- 54 touched-area regressions green (report card, LoRA train tab, compare
  window, run records, training report). ruff/py_compile clean.
- Targeted only; no suite/GPU/benchmark per the resource rule. Live end-to-end
  against a real training run is unverified — same flagged limit as #741/#742.

## Contracts for others

- **Gate E (#753, mine):** read `<run_dir>/tournament.json` — `history` rows
  `{a, b, result, ts, rating_a, rating_b}` and `promoted` are the grounded
  preference evidence.
- **Codex:** implementation review per the Gate D pattern.

## Follow-up: the "keep draft" blocker (Codex #782 review)

Codex blocked Gate D's integration on "ordinary training still doesn't
generate checkpoint sample grids." Fixed on this branch:

- `DiagnosticsLogger.save_sample(image, step, epoch)` — persists
  `samples/step-NNNNNN.png` beside the JSONL sink + a `{"step","ts",
  "sample"}` event; dead-sink/disk-error safe. Same API and on-disk
  contract as #779's copy (either side merges cleanly).
- `log_sample_grid(..., epoch=None, generator=None)` — epoch flows to the
  grid event; generator is test-injection only (production keeps the
  fixed-seed CUDA generator).
- New `backend/src/models/tuning/sample_grids.py`: `default_sample_prompts
  (trigger)` + `build_sampling_pipe(...)` composing a diffusers pipeline
  from components the trainer already holds (no base-model reload;
  py_compile/stub-verified only — no GPU run per the resource rule).
- `LoRATunerV2.train`: samples at every `_save_checkpoint` point and at
  `_save_final` with `cfg.validation_prompts` (else defaults) and
  `cfg.validation_seed`; new config knob `sample_grids: bool = True`.
  `LoRATuner.train` (V1, no per-epoch checkpoints): one final grid built
  from its `instance_prompt` — a V1-only run still can't tournament
  (support limit, documented).
- Fail-soft throughout: no run dir / opt-out / any sampling failure
  degrades to no grid, never a dead run. LyCORIS subprocess unchanged.
- Also landed Codex's integration catch on main's latent bug:
  `anime_training_pipeline` passed `use_wandb`/`wandb_project`/
  `use_tensorboard` into `LoRATunerConfig` after #741 deleted the fields —
  a constructor TypeError breaking every ordinary pipeline run. Regression
  test included.

Verification: 27 new/extended backend tests (save_sample events, disk-error
safety, fixed-prompt grid persistence, pipe routing, trainer gates +
failure swallowing, pipeline regression); 97 backend + 54 GUI targeted all
green; ruff/py_compile clean. No GPU run — real diffusion sampling
unverified, flagged.
