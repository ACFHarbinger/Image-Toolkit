# Draft: M2 graph-consistency safety gate

**Status:** discussion draft; no implementation authorization. Captures the
2026-08-22 team brainstorm for Harbinger review.

## Decision requested

Replace further threshold tuning of output-only gates with an interpretable,
graph-level registration-risk gate. Existing audited signals cannot separate
the known-good `test96` from all structural catastrophes: the documented
SeamVis sweep found zero viable threshold pairs, while Ghost and Composite
inputs are inverse or uncorrelated with human judgement.

## Proposal A — registration-risk gate

Compute these pre-render, interpretable inputs:

- weighted graph connectivity and component coverage;
- robust bundle-adjustment residual distribution;
- transform-cycle inconsistency over graph loops;
- background-masked bidirectional warp-consistency error;
- disagreement between independent registration estimators when available.

Normalize each input into a bounded risk contribution. Combine them in a
documented, monotonic weighted score calibrated on a calibration slice. The
manifest records the total, every contribution, and explicit reasons. A hard
validity failure (for example, a disconnected graph) remains separately
visible rather than becoming an unexplained score.

Classifications are `high_confidence_failure`, `uncertain`, and `low_risk`.
SeamVis remains a separate rendering-risk signal; it should not be asked to
detect registration failure.

## Proposal B — evaluation protocol

Create a defect-diverse calibration split from the structural red set:

1. Keep every uniquely represented defect type in calibration.
2. Hold out only examples from defect types represented more than once.
3. Expand the red set before claiming generalization for a unique defect with
   no second example.
4. Calibrate the fixed, interpretable weights only on the calibration slice.
5. Freeze the rule and evaluate it on the held-out slice, then on the whole
   structural red set.

The unchanged M2 discriminating bar remains the outcome check: Raw ASP must
be selected for at least one known-good case and SCANS for every known
catastrophe; every choice must be reproducible from its manifest.

## Proposal C — user policy, review, and artifacts

Expose an `uncertain_result_policy` setting:

- `raw_asp` — default; publish Raw ASP if risk is uncertain;
- `scans` — conservative automatic fallback;
- `prompt` — let the user choose after seeing both outputs, the score, and
  its contributing reasons.

This is a deliberate amendment to the current M2 wording that says uncertainty
selects SCANS. It needs Harbinger approval and a roadmap update before code.

Each run retains Raw ASP, SCANS, Safe ASP/selected output, and its manifest.
Derived Raw ASP and SCANS artifacts persist until a user explicitly invokes
cleanup. Cleanup previews affected files and reclaimable space, moves only
derived Raw ASP/SCANS artifacts to Trash, and never deletes the selected output
or manifest.

## Proposal D — later ensemble research

Do not train a model for the first gate. Once a larger, defect-balanced labeled
corpus exists, evaluate an experimental ensemble combining the graph signals
with selected image-frame features. Video is explicitly out of scope unless
frame-only results remain inadequate or a research result makes temporal input
necessary. The ensemble must improve on the frozen interpretable baseline on
a held-out, defect-stratified evaluation before it affects product selection.

## Suggested cheap first probe

Extract the candidate registration signals from existing pipeline telemetry,
run the current correlation/audit tooling on the calibration/hold-out split,
and test whether the frozen rule places `test96` and every catastrophe on the
required sides. This is measurement work only; do not alter selection behavior
until the evidence clears the protocol above.
