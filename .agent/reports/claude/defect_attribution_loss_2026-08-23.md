# Ground-truth data loss: `defect_attribution` dropped from all 97 labels — 2026-08-23

## What happened

`submodules/ASP/data/benchmarks/asp_evaluations_20260823.json` — Harbinger's
completed 97/97 re-evaluation, the single source of truth for every label-based
claim this session — **no longer contains the `defect_attribution` field on any
entry.** It did at 18:56 today; it does not at 20:08.

Verified:

- At ~18:56 I ran the differential-prevalence analysis reading
  `entry['defect_attribution']['asp']` and got populated per-comparator data
  (`asp:color_shift` 26, `asp:banding` 23, `simple:crop_loss` 14,
  `hugin:geometry_warp` 7, etc. across the 27 raw-ASP losses).
- Now: `sum(1 for e in lab.values() if e.get('defect_attribution'))` == **0 / 97**.
- File mtime is `2026-08-23 20:08:42`. Exactly one entry has an `updated_at`
  in that minute: `asp_test01`, at `2026-08-23T20:08:42`.

## Mechanism

The graded-severity schema change (`c5bb7ea` "grade defects per output" +
`5855713`) replaced `defect_attribution` with
`defect_severity[output][defect] = 1..3`. But `RatingEntry.from_dict`
(`backend/benchmark/evaluation/other/schema.py:245`) builds the entry from an
**explicit allowlist of keys**, and `defect_attribution` is not among them —
`grep -rn defect_attribution backend/ --include=*.py` returns nothing at all
now. `to_dict` therefore cannot re-emit it.

Consequence: **any save through the new schema rewrites the entire file and
silently discards the field for every entry**, not just the one being edited.
The inspector saves the whole dictionary, so editing one case destroys the
attribution data on all 97.

That is what happened. At 20:08:42 someone opened the inspector against the
live ground-truth file and graded `asp_test01` — all nine of its defects at
severity `1` ("trace"), which directly contradicts Harbinger's own note on that
case (*"ASP has every flaw except geometry warp"*). That is a smoke test, not a
judgment, and it was performed against production ground truth.

## Aggravating factors

1. **The ground-truth file is untracked by git.** `git ls-files data/benchmarks/`
   is empty. No version history, no recovery point, no backup — the inspector
   has no backup logic either (`grep -rn '\.bak\|shutil.copy'` over
   `backend/benchmark/evaluation/` returns nothing).
2. `docs/website/public/data/asp_evaluations.json` is the stale Aug-21 copy and
   never had attribution, so it is not a recovery source.
3. The only other copies on disk are pytest fixtures under `/tmp/pytest-of-*`.

## What I have preserved

Backups of the current (post-loss) file:
`data/benchmarks/asp_evaluations_20260823.backup.json` and a scratchpad copy.
The `preference`, `notes`, `defects` (flat union), `bboxes`, `edges`, and score
fields are all intact — **only the per-comparator attribution is gone.**

Recoverable from my 18:56 analysis output, for the 30 rated non-fallback cases
(ASP-attributed tags, seam and content clusters only — `color_shift`,
`crop_loss` and `ghosting` attributions were not printed per-case and are lost):

| case | pref | ASP seam tags | ASP content tags |
|---|---|---|---|
| test01 | simple | banding, blur, seam_line | duplicated_strip, misordered_content, torn_anatomy |
| test03 | simple | blur | — |
| test04 | simple | — | torn_anatomy |
| test05 | simple | banding, seam_line | — |
| test08 | simple | banding, blur, seam_line | misordered_content |
| test10 | simple | banding, blur | misordered_content, torn_anatomy |
| test17 | simple | seam_line | — |
| test22 | simple | banding, blur, seam_line | misordered_content, torn_anatomy |
| test24 | simple | banding, blur, seam_line | misordered_content, torn_anatomy |
| test26 | simple | banding, seam_line | misordered_content, torn_anatomy |
| test28 | simple | banding, seam_line | duplicated_strip, torn_anatomy |
| test37 | simple | banding, blur, seam_line | — |
| test40 | asp | banding, blur, seam_line | misordered_content |
| test41 | simple | banding, blur, seam_line | duplicated_strip, misordered_content, torn_anatomy |
| test42 | simple | banding, blur, seam_line | — |
| test53 | simple | banding, seam_line | torn_anatomy |
| test56 | simple | banding, blur, seam_line | misordered_content, torn_anatomy |
| test62 | simple | banding, blur | duplicated_strip, misordered_content, torn_anatomy |
| test65 | simple | banding, blur, seam_line | duplicated_strip, misordered_content, torn_anatomy |
| test67 | asp | — | — |
| test68 | simple | banding, blur, seam_line | duplicated_strip, misordered_content, torn_anatomy |
| test71 | simple | banding, blur, seam_line | misordered_content, torn_anatomy |
| test73 | asp | — | torn_anatomy |
| test74 | simple | banding, blur, seam_line | duplicated_strip, misordered_content, torn_anatomy |
| test78 | simple | banding, blur, seam_line | — |
| test80 | simple | blur, seam_line | duplicated_strip, misordered_content, torn_anatomy |
| test81 | simple | banding, blur, seam_line | misordered_content, torn_anatomy |
| test82 | simple | banding, blur, seam_line | duplicated_strip, misordered_content, torn_anatomy |
| test83 | simple | banding, blur, seam_line | duplicated_strip, torn_anatomy |
| test91 | simple | banding, blur, seam_line | torn_anatomy |

Aggregate ASP-attributed counts over the 27 raw-ASP losses, also from the 18:56
run and also still valid: color_shift 26, banding 23, seam_line 23, blur 21,
ghosting 20, torn_anatomy 20, misordered_content 16, duplicated_strip 10,
crop_loss 7. Non-ASP: simple color_shift 15, simple crop_loss 14, simple
torn_anatomy 3, hugin geometry_warp 7, hugin torn_anatomy 2.

## Effect on the published analysis

`asp_quality_defect_analysis_2026-08-23.md` was computed from the intact
attribution data and its numbers stand as recorded. They are **no longer
reproducible from the current file** — recomputing today falls back to the flat
`defects` union, which mixes ASP/simple/hugin defects together and shifts every
figure (e.g. `crop_loss` 72% vs 59%, `geometry_warp` flips to −9 because it is
hugin-attributed). The two-cluster conclusion survives either way; the exact
percentages do not.

## Recommended fixes

1. **Track the ground-truth file in git**, or move it somewhere that is. It is
   the most valuable artifact in this effort and it has no version history.
2. **Make `from_dict`/`to_dict` preserve unrecognised keys** so a schema change
   can never again silently delete a prior field on save.
3. **Write a `.bak` on every inspector save.**
4. **Never smoke-test the inspector against the live ground-truth file** — use a
   fixture copy. The bogus `asp_test01` severity-1 grades should be cleared;
   I have not touched them, since mutating ground truth is Harbinger's call.
