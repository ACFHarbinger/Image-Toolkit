# test94 CleanCP benchmark — 2026-08-24

Authorized one-case run in isolated input workspace
`/tmp/asp-test94-cleancp-RulVDV`; source corpus was not written. Environment:
`ASP_CLEANCP_RESOLVE=1`, deterministic seed 1729, all CPU/BLAS thread caps 1,
CUDA allocator expansion/cache flush enabled, P1/P2 switches off.

Result: the historical `affine_invalid:ratio=3.12211>3` did **not** reproduce.
Smart selection chose 13/105 frames; spatial dedup left 12; filtering retained
18 edges; the graph was connected and bundle adjustment completed. Safe ASP
fell back later on `seam_vis_gate:asp=91.4_sim=1.1_limit=35.0`; final ASP and
SCANS outputs were therefore identical. The generated report is
`/tmp/asp-test94-cleancp-RulVDV/output/benchmark_report.md`.

This does not prove CleanCP recovered the prior seven missing adjacent links:
the canonical benchmark JSON retains only the policy-facing summary, not the
pipeline session artifacts, and this selection path did not reach the old
ratio failure. The new default-off trigger and its telemetry remain unit-tested
(38 focused tests); a later reproduction must retain the frozen prior frame
selection and export `cleancp_recovery`/`affine_health` artifacts.
