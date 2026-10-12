# #746 — Training Report Card (Gate D.6)

Taken over from Qwen's slot per Harbinger's direction (Qwen never
confirmed after Claude's status post). Delivered as draft PR #777,
commit `4d185cfb`, branch `dl-d-746-report-card` stacked on Mistral's
`dl-d-741-diagnostics-wiring` (`4ee486bf`, PR #775) — retarget to `main`
after #775 lands. Worktree `~/Downloads/Data/Tests/dl-d-746`. Basis:
Qwen's proposal §4.2, #741's `record.json`/`events.jsonl` contracts,
`AdvisorFinding` from #744.

## What shipped

- `backend/src/core/training_report.py` (pure): `generate_training_report(
  events, *, rank_utilization=None, dataset_findings=()) -> ReportCard`.
  - Q1 Did it learn: EMA-smoothed loss delta over first/last ~20%
    windows; green >50% / yellow 20–50% / red <20% / info <2 points.
  - Q2 Is it overfitting: train/val gap (>20% warns) when val loss is
    logged; rank utilization bands — saturated <30% of chosen rank,
    pinned ≥95%, else healthy (14/32 healthy per the issue; 6/64
    saturated per #743's semantics). Missing halves are info rows and
    never dilute an available good verdict.
  - Q3 What to try next: dataset hygiene (duck-typed findings:
    near-dups → captions → entanglement → thin clusters) → divergence →
    plateau (step named) → rank advice; clean runs say so.
- `TrainingReportCardDialog`: non-modal card, colored status dots,
  suggestion banner, Open Run Folder.
- `LoRATrainTab`: `training_finished_signal` gains run dir as third
  payload; success with events shows the card instead of the plain
  success box; falls back when the run recorded nothing. Cancel/error
  unchanged.
- Follow-up `8cf207bd` on #774's branch adds `AdvisorPanel.findings()`
  so the integration lights up with no further changes.

## Evidence

- 23 backend + 10 GUI tests (incl. end-to-end from a real `start_run` +
  written `events.jsonl`).
- Targeted: 73 passed (report + #741 suites + card), `--run-gui`;
  ruff/py_compile clean. One pre-existing lycoris test updated for the
  3-payload signal. `test_training_event_tail` flaked once under load,
  4/4 and full-set green after — passes on the pristine base too.
- No suite/GPU/benchmark run (resource rule).

## Integration surface

- **#743 (Mistral):** wire `RankUtilization(effective, chosen)` at
  finish time when the rank chart lands — one call site in
  `_show_report_card`.
- **#742/#745/#747:** untouched; the card is the 5-second answer, their
  charts are the dig.
