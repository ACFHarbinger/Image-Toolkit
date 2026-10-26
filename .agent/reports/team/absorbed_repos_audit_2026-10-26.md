# Audit of the four absorbed repos before archiving (#867)

Read-only, 2026-10-26. Nothing was archived or changed upstream.

| Repo (in-tree dir) | Upstream main | Absorbed at | Gap | Open upstream |
|---|---|---|---|---|
| Hybrid-Image-Editor (`submodules/HIE`) | `7cb87bab9` | `7cb87bab9` | none | 6 Dependabot PRs, 3 issues |
| Cel-Shaded-Generator (`submodules/CSG`) | `616125dde` | `616125dde` | none | 10 PRs (Dependabot), 30 issues |
| Content-Recommendation-Engine (`submodules/CRE`) | `9f97f4ab9` | `9f97f4ab9` | none | 3 Dependabot PRs, 0 issues |
| Anime-Stitch-Pipeline (`submodules/ASP`) | `8763a2661` | `9ff744ae2` | **11 upstream commits, 57 files, not absorbed** | 2 Dependabot PRs, 19 issues |

All four are public, 1 star, 0 forks, none archived. Non-main branches exist only on ASP (5: `ci/e1-green-main`, `feature/433-plate-frame-cover`, `fix/e4-paramiko-constraint`, `fix/mypy-empty-container-annotations`, `fix/472-edgeless-compose`); each is 0 commits ahead of upstream main, so they hold nothing unique. The remaining branches are Dependabot and `gh-pages`.

## Blocker: ASP drift

Upstream ASP moved after the import: CI fixes (Sept 20), js-yaml bump, a mypy-annotation fix (Oct 2, touching `alignment/`, `core/`, `ingestion/`, `rendering/`), and `bench/resource-guard-9ff744a` (PR #62, Oct 14). A plain `git subtree pull` fails ("unrelated histories", because the import commits were rewritten when author names were fixed). Applying `git diff 9ff744ae..main` as a patch under `submodules/ASP` works for 52 files and conflicts in 5: `backend/src/core/pipeline/manager.py`, `backend/src/models/wrappers/efficient_loftr_wrapper.py`, `backend/test/alignment/test_canvas.py`, `backend/test/alignment/test_filter_edges.py`, `docs/website/package-lock.json`. The in-tree copy diverged from upstream during W0-03a.

## What would break on archive

Nothing found. No script or workflow clones or fetches the old repos. `submodules/{HIE,ASP,CSG,CRE}` are ordinary directories and the CMake, pyproject, justfile and ledger references are local paths.

Stale pointers to tidy (not blockers):
- `docs/website/src/constants/submodules.ts` links to the old repo URLs.
- `.github/workflows/docs.yml` lychee excludes for the old `moon/` URLs; `.github/dependabot.yml` comment.
- `docs/website/public/docs/DEVELOPMENT.md` still says `git submodule update --init --recursive`; `git/scripts/_submodule_bootstrap.py` and `tools/*/justfile` still use the submodule wording.
- Old issues (ASP 19, CSG 30, HIE 3) live only upstream; archiving leaves them readable but closed to new activity. Decide whether to move or close them first.

## Before archiving

1. Absorb the 11 ASP commits and resolve the 5 conflicts (Gemini, owner of #867).
2. Tidy the stale pointers and the `DEVELOPMENT.md` instructions.
3. Decide what to do with the open upstream issues.
4. Harbinger confirms, then archive HIE, CSG, CRE, ASP in that order (ASP last).
