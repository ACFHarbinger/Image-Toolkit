# `main` divergence investigation — local vs `origin/main`

**Date:** 2026-08-31
**Context:** v1.0.0 release prep needs local `main` on `origin` so a tag-triggered
Actions release can run. Local `main` and `origin/main` had diverged; the user
asked for an investigation before reconciling ("investigate, then merge after
identifying the blobs that were stripped to remove them").

## Finding: `origin/main` has ZERO unique content

```
git cherry HEAD origin/main   →   873 commits, ALL marked "-", 0 marked "+"
```

Every commit on `origin/main` has a patch-equivalent already present on local
`main`. Local `main` is `origin/main`'s history **rewritten** (large-blob strip
via filter/rebase — the duplicate commit-message pairs in `git log` are the
rewrite twins) **plus ~6 more days of work** (up to `da54f66f`, 2026-08-29).
`origin/main` is frozen at `692cba16` (2026-08-23, "Fixed ruff issues").

Working-tree diff `HEAD..origin/main` is only 77 files. Spot-checked
`backend/src/models/wrappers/birefnet_wrapper.py`: `origin/main` holds the
**old** version (plain `torch.no_grad()`), local holds the `e720ccd1` VRAM /
OOM-self-heal fix. i.e. moving toward `origin/main` is a regression, not a merge
gain. Same story for the other 76 files — local is strictly ahead.

## What the strip removed

Backup ref `backup/pre-strip-locked-renderers` still carries the pre-strip tree.
Delta vs local `HEAD`: **118.7 MB across 51 binary files**, all
review/export image bundles that violate the AGENTS.md "no PNG bundles in git
history" rule:

- `.agent/reports/chat/locked_renderer_exports_2026-08-24/asp_test*/{baseline,p1_single_pose,p1p2_multiband}.png` (1.7–2.6 MB each)
- `.agent/reports/chat/locked_renderer_case17_regen_2026-08-27/{baseline,p1,p1p2}.png`
- `.agent/reports/.../locked_renderer_visual_review/asp_test*/...png`
- a handful of `docs/website/public/**` binaries (hero images, `coherence_v2/*.png`, bibliography PDFs)

No source, config, lockfile, or doc-text content was lost in the strip — only
generated image bundles.

## Recommendation: force-push, do **not** merge

`git merge origin/main` is the wrong tool here:

1. It would **resurrect the 118.7 MB of stripped blobs** through the merge
   (they still exist on `origin`'s side of the history).
2. It would graft 873 redundant pre-rewrite commits back onto `main`.
3. It gains **nothing** — `git cherry` proves there is no unique content to
   recover.

Correct reconciliation:

```bash
git fetch origin
# snapshot the old remote head first (recoverable for 90d via reflog anyway)
git push origin origin/main:refs/backup/origin-main-2026-08-23
git push --force-with-lease=main:692cba16e8216877f14602ae38f975701f6f5ee3 origin main
```

`--force-with-lease` pinned to the known SHA fails safely if `origin/main`
moved since this fetch. This repo is single-remote, single-author — no other
consumer of `origin/main` to break.

## After the push

- `origin/main` == local `main` (`da54f66f`), 118.7 MB lighter.
- Dependabot PR branches on `origin` were cut from the old history — they will
  show huge diffs / conflicts. Close and let Dependabot re-open them against the
  new base, or rebase manually. Not release-blocking.
- `backup/pre-strip-locked-renderers` (local) and
  `refs/backup/origin-main-2026-08-23` (remote) are the recovery points; keep
  both until v1.0.0 ships, then they can go.
