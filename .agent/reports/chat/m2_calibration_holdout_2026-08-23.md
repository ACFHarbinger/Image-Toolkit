# M2 calibration / hold-out baseline — 2026-08-23

## Corpus and labels

- Run: `submodules/ASP/backend/benchmark/output/anime_stitch_latest_consolidated.json`
- Coverage: **97/97** datasets
- Labels: `docs/website/public/data/asp_evaluations.json`
- Human score-order split: 10 Raw-ASP-preferred, 38 ties, 49 SCANS-preferred
- Score-order known-good set: `21, 44, 46, 51, 52, 56, 58, 61, 89, 96`
- Discriminating catastrophes: `04, 06, 07, 12, 14, 15`

## Existing rendered-output gates

The full-corpus gate-signal audit used all 97 reviewed rows. Oriented
Spearman correlations against human ASP-minus-SCANS score were:

| Signal | rho | p |
|---|---:|---:|
| Seam visibility | +0.085 | 0.4094 |
| Seam gradient | +0.076 | 0.4595 |
| Seam coherence | +0.067 | 0.5122 |
| Strip banding | +0.009 | 0.9333 |
| Ghosting SIQE | -0.061 | 0.5500 |
| Coverage | -0.173 | 0.0908 |

The existing gates therefore provide no statistically clear full-corpus
calibration signal. The SeamVis sweep remains infeasible: zero threshold
pairs reject all six catastrophes while retaining the named known-good
`asp_test96`.

## Registration telemetry screen

The completed run contains per-pair telemetry, cycle error, and bundle
adjustment residuals. On the 16-case discriminating red set, a transparent
exploratory high-risk rule of:

```text
BA residual missing OR BA RMS > 80
OR cycle error RMS > 300 OR raw edge count <= 10
```

classifies all six catastrophes as high-risk and retains five of the ten
score-order known-good cases (`44, 56, 58, 61, 96`) as low-risk. This is
evidence that registration-stage signals may cross the M2 bar; it is not yet a
hold-out result because the thresholds were selected while inspecting the red
set.

## Decision

The corpus is ready for the formal calibration/hold-out pass. The next valid
step is to freeze the rule and split before evaluating the held-out cases;
existing SeamVis/Ghost/Composite thresholds must not be retuned against the
hold-out. No production gate or default has been changed by this analysis.

### Pre-registered defect-stratified hold-out

The held-out membership was selected before the refit by assigning each role
to a stable SHA-256 bucket and taking bucket 2 of 4. This retains both roles
in hold-out while avoiding telemetry-dependent case selection:

| Split | Catastrophes | Score-order known-good |
|---|---|---|
| Calibration | `04, 06, 12, 14, 15` | `21, 44, 51, 52, 56, 58, 96` |
| Held out | `07` | `46, 61, 89` |

Every defect tag in the held-out rows is also represented by at least one
calibration row, satisfying the protocol's requirement not to hold out a
uniquely represented failure type.

The calibration-only grid fit selected `BA RMS > 80`, cycle RMS `> 300`, and
raw edges `<= 10`, with missing BA treated as high-risk. It rejected all five
calibration catastrophes and retained four of seven calibration known-good
cases (`44, 56, 58, 96`). Without refitting, it classified held-out
`asp_test07` as high-risk and held-out `asp_test61` as low-risk; the remaining
two held-out known-good cases (`46, 89`) were conservatively high-risk.

This passes the M2 discriminating bar on the held-out slice, but the hold-out
is four cases. It is a feasibility result, not a generalization or
production-gate approval. A formal M2 implementation must retain this split
and repeat the frozen evaluation before promoting the rule.

### Repeated pre-registered buckets

The same hash-bucket protocol was repeated for all four buckets. Each fit used
only its calibration rows; every calibration fit independently selected the
same rule (`BA RMS > 80`, cycle RMS `> 300`, raw edges `<= 10`, or missing BA).
Every held-out defect tag was represented in its corresponding calibration
slice.

| Held-out bucket | Held-out catastrophes | Held-out known-good | Frozen result |
|---:|---|---|---|
| 0 | `04, 12, 15` | `58` | all catastrophes high-risk; `58` low-risk |
| 1 | `06, 14` | `21, 44, 52, 56` | all catastrophes high-risk; `44, 56` low-risk |
| 2 | `07` | `46, 61, 89` | `07` high-risk; `61` low-risk |
| 3 | none | `51, 96` | `96` low-risk; all six catastrophes remained in calibration and high-risk |

Across the four rotations, every named catastrophe was evaluated either in a
held-out bucket or in that bucket's frozen calibration rule, and every bucket
retained at least one held-out or calibration known-good case. No bucket
required a threshold refit. This strengthens the result to repeated
pre-registered feasibility evidence; the sample remains too small to claim
generalization or enable a production policy.
