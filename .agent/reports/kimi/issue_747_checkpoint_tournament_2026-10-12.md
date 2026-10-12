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
