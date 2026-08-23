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

### Illustrative frozen split

For a first bounded check, the first eight score-order known-good IDs were
used for calibration and `asp_test89`, `asp_test96` were held out. A grid fit
on the calibration portion selected the same simple thresholds shown above
(`BA RMS > 80`, cycle RMS `> 300`, raw edges `<= 10`, with missing BA treated
as high-risk):

- Calibration: all 6 catastrophes rejected; 4/8 known-good cases retained.
- Hold-out: `asp_test89` rejected as high-risk; `asp_test96` retained as
  low-risk.

This is a useful positive feasibility result, but the two-case hold-out is too
small to support a generalization claim. A formal M2 implementation should
pre-register a defect-stratified split and repeat the frozen evaluation before
promoting the rule.
