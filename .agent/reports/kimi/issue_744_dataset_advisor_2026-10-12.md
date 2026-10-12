# #744 — Dataset advisor (Gate D.4)

Taken over from Qwen's slot per Harbinger's direction. Delivered as draft
PR #774, commit `b130e95c`, branch `dl-d-744-dataset-advisor` off `main`
(Gate D is parallel-safe with B/C), worktree `~/Downloads/Data/Tests/dl-d-744`.
Design basis: Qwen's proposal §4.3 (two-panel layout) and §4.4 (C++
tradeoff — validated against, not taken), Gemini's entanglement formula
folded in per the delegation round.

## What shipped

- `backend/src/core/dataset_advisor.py` (pure, torch-free):
  - `scan_dataset`: sha256 + PIL header probe (unreadable files), aspect
    outliers (>3:1), caption sidecar coverage, exact-hash duplicates with
    video-frame grouping (trailing-digit stems → scenes; intra-scene =
    informational burst, cross-scene = excludable), tag entanglement
    `Ent(T,trigger)=P(T∩trigger)/P(T) > 0.85` (min support 5, composition
    tags skipped), mtime+size hash cache for cheap re-scans,
    progress/cancel hooks.
  - `analyze_diversity(embeddings)`: near-dup clusters (cos ≥ 0.98,
    union-find), spherical k-means, dominant-mode (>60%) and thin-cluster
    findings, diversity index. **sklearn deliberately avoided**: its first
    `KMeans.fit` walks every loaded shared library via threadpoolctl and
    stalled >6 s inside a GUI worker thread (traced with faulthandler);
    hand-rolled k-means is deterministic and house style anyway (the
    similarity engine clusters with C++ HNSW + union-find).
- `gui/src/components/dialogs/dataset_advisor_panel.py`: finding cards
  with one-click actions (Show / Exclude / Hydra chip / Review Tags);
  findings without an honest one-click fix render informational, no
  button (the issue's own rule). Hydra chips are removable, appended to
  the `hydra_dispatch` command, shown in the effective config summary.
  Clustering worker holds the GPU lease as `dataset-advisor`.
- `LoRATrainTab`: left = vertical splitter (form + `VirtualGallery`
  contact sheet); right = QTabWidget(Advisor, Review Tags — the existing
  embedded panel, object unchanged). Exclusion set threads into
  `resolve_imported_dataset`; folder scope restages so training cannot
  see excluded files; Restore restages the original. `prepare_dispose`
  stops advisor workers.

## Evidence

- 16 backend tests + 17 GUI tests (panel 9, tab wiring 8 incl. the full
  exclude→restage→restore round-trip on a real tmp folder).
- Targeted: 64 passed (advisor backend+GUI plus pre-existing
  lycoris/tag-review suites) with `--run-gui`; ruff/py_compile clean.
- No suite/benchmark/GPU run (resource rule).

## Integration surface for Gate D

`AdvisorFinding` dataclass (category/severity/title/paths/action/
action_payload) is the reuse point — #746's report card can consume it
directly; no training-run signals are touched (#741 stays clean).
