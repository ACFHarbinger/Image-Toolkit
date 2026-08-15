# Analytics and Defect Glossary

Living shared vocabulary for Image Toolkit and ASP analytics. This is the
human-readable companion to the versioned JSON/Parquet artifact contract in
[`analytics_and_interpretability.md`](analytics_and_interpretability.md).
Add terms only with a definition, measurement direction where relevant, and a
clear distinction from nearby terms.

## Result identities

- **Raw ASP** (`raw_asp`): the ungated ASP compositor result. It remains an
  artifact even when a policy selects another result.
- **Safe ASP** (`safe_asp`): the policy-selected ASP-safe result; it may use a
  named safe fallback but is not a fourth result identity.
- **SCANS** (`scans`): the OpenCV stitcher comparison/fallback result.

## Defect labels

- **ghosting**: doubled or semi-transparent visual content caused by imperfect
  alignment or overlap composition.
- **seam_line**: an unwanted visible boundary at or near a stitch seam.
- **misordered_content**: spatial or temporal content appears in the wrong
  sequence/order.
- **crop_loss**: meaningful intended content is missing from the output bounds.
- **torn_anatomy**: character/object anatomy is discontinuous or implausibly
  joined across a composition boundary.
- **duplicated_strip**: a scene strip or content region appears more than once.
- **banding**: discrete tonal/color steps where a smooth transition is expected.
- **color_shift**: unwanted color or luminance change relative to the intended
  source/reference.
- **blur**: loss of meaningful high-frequency detail beyond expected scaling or
  motion characteristics.
- **geometry_warp**: visibly implausible shape distortion from the transform.

## Evidence and decisions

- **observation**: an individual human or automated claim about a metric,
  defect, or safety decision; it is retained even when later disagreed with.
- **adjudication**: a separately stored, reasoned effective decision over one
  or more observations; never a destructive replacement for them.
- **provenance**: enough information to reproduce or assess a claim: producer
  and version, inputs/hashes, configuration, timestamp, and evidence links.
- **primary defects**: one or more defects judged equally causal for a case;
  not a forced single-label classification.
