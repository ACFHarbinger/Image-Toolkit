# #753 — Evidence-traced suggestions, abstention as first-class output, confidence display

Date: 2026-10-12 · Author: Kimi · Branch: `dl-e-753-evidence-confidence` (stacked on `dl-e-751-guidance-schema`, PR #785) · PR: (this branch)

## What shipped

**Schema v1 extension** (`backend/src/core/guidance_schema.py`, additive —
Mistral's validators untouched, her 23 tests stay green): per-change
optional `evidence[]` (`EvidenceRef{kind, ref, summary}`) + `confidence`
(0–1); top-level optional `needs[]` + `diagnosis`. All parsed tolerantly —
malformed evidence is dropped, garbage confidence ignored, non-list needs
skipped: an optional v1 extension never fails an otherwise-valid response.
Kinds: `tournament | advisor_finding | run_record | training_metric | ocr | vlm`.

**Pure engine** (`backend/src/core/guidance_evidence.py`, torch-free):

- `resolve_evidence()` — tournament refs read the real `tournament.json`
  (#747 contract: leader/promoted ELO ± margin over N blind comparisons);
  run records read `record.json` (#741); advisor findings carry importable
  image paths. Missing artifacts render **stale**, never an invented
  summary. OCR/VLM signals are summary-only until Grok's advisor emits
  artifact-backed refs.
- `gather_run_evidence(run_dir)` — the local measured signals a suggestion
  can cite: record + tournament + promoted checkpoint.
- `compute_confidence()` — Qwen's §5.3 rubric literal: base 0.5, ±0.2 on
  the premise-validator outcome, +0.1 per additional agreeing signal kind
  (cap +0.3), −0.25 per contradiction (`{"polarity": "contradicts"}`),
  advisor score blends as a 0.3 prior, stale/hallucination caps below
  medium. `confidence_for_change()` maps a `SuggestionVerdict` to
  verified/flagged. Bands: ≥0.8 high/green, 0.5–0.8 medium/yellow,
  <0.5 low/red + abstention hint.
- `needs_pick_list()` — prefiltered existing image paths for the handoff.

**GUI** (`gui/src/components/guidance/guidance_evidence_widgets.py`):

- `ConfidenceBadge` — colored dot + label per band, tooltip shows the
  numeric score.
- `EvidenceChipBar` — clickable chips (folder chips open the artifact,
  advisor chips emit `paths_requested`); stale chips gray, dashed, marked.
- `EvidenceRowExtras` — badge + chips as one embeddable row payload.
- `AbstentionPanel` — "Insufficient evidence — capture these:" with the
  needs list, diagnosis, prefiltered-count, and a send button that
  publishes `ImportPathsIntent(module_id="dl.train", origin="guidance")`
  on the event hub — the workspace host's existing handler routes it to
  Train's dataset panel (`apply_imported_paths`, live on main). Works with
  or without a hub (signal fallback).

## Verification

- 22 new backend tests (parse extension + tolerance, rubric arithmetic,
  band thresholds, resolution against real `tournament.json`/`record.json`
  fixtures incl. stale paths, `gather_run_evidence`, pick-list).
- 9 new GUI tests (badge bands, chip rendering/clicks/signals, row
  extras, abstention render + intent dispatch + no-hub fallback).
- Regressions green: Mistral's 23 schema tests, tournament/run-records/
  report suites, tournament dialog, report card (115 backend + 35 GUI
  targeted total). ruff/py_compile clean. No suite/GPU/benchmark.

## Integration notes (for Codex's Gate E merge)

- Chips + badge slot into Muse's `_add_row()` in
  `guidance_diff_widget.py` (reason render, ~line 255): one
  `EvidenceRowExtras(change, validation, runs_root=...)` per row.
- `AbstentionPanel` hosts under the widget when `response.needs` is
  non-empty, fed with the response's evidence refs.
- #751's branch base: this PR targets `dl-e-751-guidance-schema`; retarget
  to main after #785 lands (same Gate B/D stacking pattern).
