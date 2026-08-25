# test94 frozen-selection CleanCP reproduction — 2026-08-25

Authorized one-case reproduction, deterministic seed 1729 and one CPU/BLAS
thread. It used the frozen 13-frame selection and disabled spatial dedup only
for this measurement (`SPATIAL_DEDUP_PX=0` at runtime); source data was not
written. CleanCP remained default-off in product code and was enabled only via
`ASP_CLEANCP_RESOLVE=1`.

It reproduced the hard registration failure: `affine_invalid:ratio=3.90229 >
3`, then correctly fell back to SCANS. CleanCP was accepted and reduced missing
adjacent edges from 7 to 3 (33 raw / 29 post-filter edges; 2,060 control points
removed; four consensus candidates rejected), but did not alter the final
affine spacing: max/median/min gaps were 134.662/34.509/18.579 px before and
after recovery. This is partial connectivity recovery, not a ratio rescue; no
ratio threshold/default was changed.

Full session artifact: `/tmp/asp-test94-frozen-Mha1nw/session.json`.
