# M2 gate-signal design review — GhostGate, CQAS, and hold-background flag

**Reviewer:** Chat/Codex  
**Scope:** review Claude's M2 correlation audit; specify the safe next change
for `GhostGate` and `cqas`; reconcile the `ASP_HOLD_BG_SUB` roadmap wording.
No pipeline defaults are changed by this review.

## Audit verdict

The method is appropriate for its stated question: it pairs each reviewed case's
ASP-minus-SCANS metric delta with that case's human ASP-minus-SCANS score delta,
then uses a direction-normalised Spearman rank correlation.  Rank correlation is
a sensible first screen because the labels are ordinal and no linear metric-to-
quality relation is claimed.

I independently reran the audit against the saved 2026-08-07 97-case run and
the completed human labels.  Results reproduce Claude's conclusions:

| Signal | Rho | Review decision |
| --- | ---: | --- |
| `ghosting_siqe` / `ghosting_score_v2` | -0.600 | Cannot remain an automatic fallback signal. |
| `seam_visibility` | +0.425 | Retain `SeamVisGate` as the current validated safety gate. |
| `seam_gradient` | +0.473 | Useful supporting telemetry; candidate for later validation. |
| `cqas` | -0.091, non-significant | Not a quality-ranking scalar. |
| `seam_coherence` | -0.062, non-significant | Telemetry only. |
| `strip_banding_score` | -0.525 date-locked, n=12 | Demotion candidate, but insufficient alone to calibrate a new threshold. |

The result is a screening result, not a complete causal validation: labels
compare whole outputs, existing 2026-08-07 artifacts predate the post-M1
adapter, and the saved post-M1 output lacks a single consolidated 97-case
metrics file.  Those limits do not rescue an inverse signal; they do mean a
replacement must be tested independently rather than inferred from the same
correlation table.

## GhostGate: retire as a decision gate; preserve as telemetry

Do **not** substitute `seam_visibility_score` directly into `GhostGate`.
That would create two names, thresholds, and fallback reasons for one already
validated seam-discontinuity test, which obscures rather than improves an
explainable Safe ASP decision.

The one-change M2 experiment should instead:

1. Disable `GhostGate`'s reject/fallback decision under the candidate policy.
   Its `ghosting_score_v2` value remains recorded as telemetry with an explicit
   `telemetry_only_inverse_validated` status.
2. Keep `SeamVisGate` unchanged as the sole currently validated rendered-image
   fallback gate.  Keep its existing SCANS-relative comparator and reason code.
3. Do not introduce a new "ghost" gate until M2.5 has a per-output double-edge
   or foreground-overlap diagnostic and validates it separately on held-out
   human-labelled cases.  A candidate must detect structural double images,
   not merely relabel seam discontinuity.

Promotion ladder for this one change: five-case screen including an historic
GhostGate-only fallback and a known-good ASP selection; stratified structural
red-set screen; then all 97.  The candidate must not introduce a human-worse
selection, must remain discriminating, and must retain raw/safe/SCANS evidence
and per-gate reason traces.  Until that is complete, this is a design decision,
not a default flip.

## CQAS: retire v1 from ranking, do not hand-tune a v2

`cqas` v1 is a reporting aggregate, not a safety gate.  Its inverse and
no-signal inputs make a reweight based only on the current table unjustified.
Giving seam visibility all (or nearly all) of the weight would merely duplicate
the existing gate and falsely imply a broadly validated quality score.

For the immediate M2 change:

- mark the current field `cqas_v1_legacy` / display it as **diagnostic only**;
  remove it from automated ASP-vs-SCANS verdicts, sort order, and success claims;
- retain component metrics individually, with their direction and validation
  status visible; and
- do not rename a new score to `cqas` without versioning and a manifest-recorded
  formula.

M2.5a owns a prospective `cqas_v2` study: derive candidate components on one
labelled development subset, freeze the formula, evaluate it on a held-out
stratified subset, then confirm it on a consolidated post-M1 all-97 run.  The
minimum candidate inputs are validated seam metrics; any ghosting/foreground
diagnostic must show non-negative held-out association before receiving weight.
Human preference and defect categories remain the authoritative comparator.

## `ASP_HOLD_BG_SUB`: resolve the apparent M2/M4 conflict

The two roadmap statements can both hold if they govern different decisions:

- **M2 now:** register `ASP_HOLD_BG_SUB` as a typed, persisted **advanced,
  experimental, default-off** configuration field.  Its manifest must record
  that it invokes the currently unaligned background-plate implementation, so
  it is not eligible for a default profile or automatic promotion.
- **M4 later:** decide whether the field survives or is removed together with
  the replacement of `_estimate_background_plate()` and integration/removal of
  the hold-DP path.  That milestone owns the algorithmic semantics, not the
  current configuration provenance.

This satisfies M2's reproducibility requirement without registering known-broken
behaviour as a supported feature, and avoids deleting the only controlled entry
point before M4 can test the corrected design.

## Reproduction

From `submodules/ASP`:

```bash
../../.venv/bin/python backend/benchmark/audit_gate_correlation.py \
  --run backend/benchmark/output/anime_stitch_20260807_045552.json \
  --labels data/benchmarks/asp_evaluations_20260810.json \
  --recompute-missing --max-image-date 2026-08-07
```

This emitted 97 paired cases for the established signals and 12 date-locked
cases for recomputed strip-banding.  No code or default configuration changed.
