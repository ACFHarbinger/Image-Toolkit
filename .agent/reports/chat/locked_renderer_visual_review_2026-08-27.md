# Locked renderer visual review — 2026-08-27

Reviewed the 13 cases remaining in #463 from
`locked_renderer_exports_2026-08-24`. Each comparison is baseline, P1, then
P1+P2.

| cases | finding | outcome |
|---|---|---|
| 03 | P1 removes the visible outline/ghosting in the baseline; P1+P2 differs only slightly from P1. | Improvement, but not enough to offset the blocker below. |
| 05 | P1 removes the conspicuous horizontal smear/band through the lower scene; P1 and P1+P2 are byte-identical. | Improvement. |
| 17 | Both P1 outputs introduce large opaque horizontal regions that remove substantial image content. | Regression; blocks sign-off. |
| 37, 42, 78 | All three arms are byte-identical. | No compositor effect to assess. |
| 01, 41, 65 | All three arms are byte-identical. | No content-integrity regression introduced by the compared arms. |
| 74, 28, 83, 73 | All three arms are byte-identical, consistent with their documented safety fallbacks. | Routing outcome acceptable. |

ImageMagick MAE confirms the visible comparisons: 03 baseline→P1 0.08097,
P1→P1+P2 0.00196; 05 baseline→P1 0.09459, P1→P1+P2 0; 17
baseline→P1 0.16171, P1→P1+P2 0.02439. The other ten reviewed cases have
zero MAE across all arms.

Decision: do not sign off on P1/P2 compositor acceptance. Investigate the
coverage/canvas handling that produces the large opaque regions in case 17,
then regenerate and review that case before reopening the acceptance decision.
