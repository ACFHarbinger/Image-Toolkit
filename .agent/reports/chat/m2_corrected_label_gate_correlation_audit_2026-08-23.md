# M2 corrected-label gate correlation audit — 2026-08-23

Inputs were frozen telemetry `anime_stitch_latest_consolidated.json` (97
datasets, SHA-256 `3daf21ca…56fc898`) and corrected human labels
`asp_evaluations_20260823.json` (97 reviewed, SHA-256 `55db3fe2…4773d9c`). No
benchmark was run.

For each case, Spearman's rho compares the human score delta
`ASP − SCANS` with the corresponding metric delta. Metrics are oriented so a
positive value means the metric claims ASP improved. Thus positive rho agrees
with human preference; negative rho is an inverse signal.

| Signal | rho | p | n | Result |
|---|---:|---:|---:|---|
| Ghosting SIQE | -0.533 | 1.96e-08 | 97 | inverse |
| Edge energy | -0.474 | 9.31e-07 | 97 | inverse |
| Seam coherence (Composite) | -0.372 | 1.77e-04 | 97 | inverse |
| Sharpness | -0.309 | 0.00209 | 97 | inverse |
| CQAS v1 legacy | -0.228 | 0.0248 | 97 | inverse |
| Coverage | -0.002 | 0.983 | 97 | no signal |
| Seam gradient | +0.217 | 0.0325 | 97 | weak positive |
| Seam visibility | +0.425 | 1.41e-05 | 97 | positive globally |
| Color entropy | +0.456 | 2.68e-06 | 97 | positive globally |
| Strip banding (Composite) | +0.512 | 8.41e-08 | 97 | positive globally |

The global SeamVis/banding association does not validate either as a reliable
selection gate: after splitting by the frozen run's selected identity,
SeamVis is non-significant for non-fallback (`rho=+0.183`, `p=0.315`, n=32)
and fallback (`rho=-0.013`, `p=0.915`, n=65) cases. Strip banding is likewise
non-significant (`rho=-0.061`, `p=0.741`, n=32; `rho=+0.158`, `p=0.207`,
n=65). Composite seam coherence remains inverse in both strata
(`rho=-0.380`, `p=0.032`, n=32; `rho=-0.265`, `p=0.033`, n=65). Ghosting is
inverse overall and in fallbacks (`rho=-0.255`, `p=0.040`, n=65).

Conclusion: the audit supports the corrected-label claim that present gates do
not provide a dependable content-plausibility discriminator. Do not recalibrate
or promote Ghosting/Composite from these correlations. SeamVis's global signal
merits diagnostic retention, but the stratum result does not justify treating
it as a proven safeguard for torn anatomy or misordered content. Content-level
evaluation remains the missing measurement track.

Reproduce with:

```bash
cd submodules/ASP
python backend/benchmark/audit_gate_correlation.py \
  --run backend/benchmark/output/anime_stitch_latest_consolidated.json \
  --labels data/benchmarks/asp_evaluations_20260823.json
python backend/benchmark/audit_defect_correlation.py \
  --run backend/benchmark/output/anime_stitch_latest_consolidated.json \
  --labels data/benchmarks/asp_evaluations_20260823.json
```
