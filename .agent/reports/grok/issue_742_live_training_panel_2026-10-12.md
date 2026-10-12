# #742 — Live training panel

Branch `dl-d-742-live-training-panel`, stacked on `dl-d-741-diagnostics-wiring` (`4ee486bf`). Draft PR base is that branch. Retarget to `main` after #775 lands.

- `LiveTrainingPanel` sits under the LoRA train form: determinate epoch bar, raw `_SparkLine` (last 64), and a loss polyline. Min/max buckets keep spikes. A trailing-mean guide is drawn on top and is not written back to `events.jsonl`.
- Scrubbing the curve maps x to a step and highlights the latest sample at or before that step. The compare pane is an embedded `ImageCompareWindow` of the previous sample and the highlighted one.
- Samples are `samples/step-NNNNNN.png` beside `events.jsonl`. `log_sample_grid` calls `save_sample`. Paths with `..` or an absolute root are ignored.
- The panel follows `TrainingEventTail`. This branch carries Codex's stale-read fix (byte offset, generation, dirty re-read) from `review/dl-gate-d`. It does not carry the Hydra `logging.run_dir` declaration, so a LyCORIS subprocess still only shows a curve when that override is accepted.
- LyCORIS starts in its own session. Cancel sends SIGTERM to the group, then SIGKILL if it is still running. The in-process cancel flag is unchanged. The success dialog stays the #741 `QMessageBox`; #746 owns the report card.

Targeted checks: 15 backend (`test_training_curve`, diagnostics JSONL + `save_sample`) and 32 GUI (panel, LyCORIS cancel, event tail) with `--run-gui`. No suite, benchmark, or GPU run.

— Grok, 2026-10-12
