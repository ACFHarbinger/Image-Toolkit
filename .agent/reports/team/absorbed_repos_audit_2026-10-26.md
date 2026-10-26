# Audit of the four absorbed repos before archiving (#867)

Read-only, 2026-10-26. Nothing was archived or changed upstream.

| Repo (in-tree dir) | Upstream main | Absorbed at | Gap | Open upstream |
|---|---|---|---|---|
| Hybrid-Image-Editor (`submodules/HIE`) | `7cb87bab9` | `7cb87bab9` | none | 6 Dependabot PRs, 3 issues |
| Cel-Shaded-Generator (`submodules/CSG`) | `616125dde` | `616125dde` | none | 10 PRs (Dependabot), 30 issues |
| Content-Recommendation-Engine (`submodules/CRE`) | `9f97f4ab9` | `9f97f4ab9` | none | 3 Dependabot PRs, 0 issues |
| Anime-Stitch-Pipeline (`submodules/ASP`) | `8763a2661` | `8763a2661` | **none (11 commits absorbed, #867)** | 2 Dependabot PRs, 19 issues |

All four are public, 1 star, 0 forks, none archived. Non-main branches exist only on ASP (5: `ci/e1-green-main`, `feature/433-plate-frame-cover`, `fix/e4-paramiko-constraint`, `fix/mypy-empty-container-annotations`, `fix/472-edgeless-compose`); each is 0 commits ahead of upstream main, so they hold nothing unique. The remaining branches are Dependabot and `gh-pages`.

## Resolution: ASP drift absorbed

The 11 upstream ASP commits (`9ff744ae..main`) were absorbed into `submodules/ASP/` across 57 files, with conflicts resolved cleanly in `manager.py`, `efficient_loftr_wrapper.py`, `test_canvas.py`, `test_filter_edges.py`, and `docs/website/package-lock.json` while maintaining monorepo path renames. Stale pointers in `docs/website/src/constants/submodules.ts`, `.github/dependabot.yml`, `DEVELOPMENT.md`, and justfiles have been updated.

## What would break on archive

Nothing found. No script or workflow clones or fetches the old repos. `submodules/{HIE,ASP,CSG,CRE}` are ordinary directories and the CMake, pyproject, justfile and ledger references are local paths.

Stale pointers tidied:
- `docs/website/src/constants/submodules.ts` links to monorepo tree paths.
- `.github/dependabot.yml` references updated to monorepo roadmap.
- `docs/website/public/docs/DEVELOPMENT.md` updated to document absorbed status (no `git submodule update`).
- Justfiles updated to drop stale submodule initialization hints.
- Old issues (ASP 19, CSG 30, HIE 3) live only upstream; archiving leaves them readable but closed to new activity.

## Archiving status

1. [x] Absorb the 11 ASP commits and resolve conflicts (Gemini, owner of #867).
2. [x] Tidy stale pointers and `DEVELOPMENT.md` instructions.
3. [ ] Upstream issues decision (remain readable upstream in archived repos).
4. [ ] Harbinger confirms, then archive HIE, CSG, CRE, ASP in that order (ASP last).
