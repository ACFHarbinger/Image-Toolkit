# Relocating the absorbed repos out of `submodules/` (#867 phase E)

Harbinger, 2026-10-26: the four upstream repos are archived; move any code that may still be updated into proper homes, then delete `submodules/`. History is already in this repo (git subtree) and in the archived upstream repos.

## Rules for every move

- Move with `git mv` so history follows. One PR per repo against `main`, no stacking. Land in this order: **CRE, CSG, HIE, ASP**, then the final removal PR. Shared files (`pyproject.toml`, `backend/CMakeLists.txt`, `justfile`s, `migration/features.toml`) conflict, so re-sync after the PR ahead lands.
- The Python engines must stay Qt-free and import lazily: the staged sidecar runtime has no numpy, Pillow or cv2 at start-up (`middleware/test/packaging`).
- No behaviour change in the move PRs. Tests move with the code and pass from the new paths.
- Run `tsc`, contracts, docs freshness, ledger and import-linter before pushing. Do not auto-merge TypeScript or `server.py`; check the result.
- Update `migration/features.toml` paths so the ledger still passes.
- Delete `_submodule_loader.py` and `git/scripts/_submodule_bootstrap.py` only in the last PR that removes their final caller.

## Target homes

| From | To |
|---|---|
| `submodules/ASP/backend/src` (Python pipeline) | `middleware/src/stitching/` (the name `core` etc. would collide with `middleware/src/core`, so the package gets one namespace) |
| `submodules/ASP/base/src` and headers | `backend/src/asp/` (C++ already shares `backend/CMakeLists.txt` since phase B) |
| `submodules/ASP/backend/test` | `middleware/test/stitching/` |
| `submodules/ASP/data`, benchmark assets | `data/asp/` (or leave out if regenerable; say so in the PR) |
| `submodules/CSG/logic`, `app`, `integrations`, `config` | `middleware/src/csg/` (+ `middleware/test/csg/`) |
| `submodules/HIE/logic`, `middleware`, `settings`, `config` | `middleware/src/hie/` (+ `middleware/test/hie/`) |
| `submodules/HIE` C++ / `desktop` / `infra` pieces still used | `backend/src/hie/`, `desktop/`, `infra/` |
| `submodules/CRE/src`, `scripts`, `tests`, `data` | `middleware/src/cre/`, `middleware/scripts/`, `middleware/test/cre/`, `data/cre/` |
| each repo's `docs/` | `docs/<asp|csg|hie|cre>/`, linked from `docs/modules/<x>.md` |
| each repo's `frontend/` | already folded into `frontend/` in phase D; remove the leftover copy |

## Not moved (deleted with the directory)

The Qt `gui/` trees (frozen, retired by #921), per-repo `.github/.gitea/.forgejo/.gitlab`, `.devcontainer`, `.agent`, `.pre-commit-config.yaml`, `CLAUDE.md`, `GEMINI.md`, `uv.lock`, per-repo `justfile`/`pyproject.toml` (fold anything still needed into the root ones), `README.md`, `LICENSE` (keep each licence text in `docs/<x>/LICENSE` if it differs from the root licence). Anything a PR author thinks must survive but is not in the table: ask on the bus first.

## Final PR (after the four land)

Tag `main` as `pre-submodules-removal`, delete `submodules/`, drop `submodules/**` from `pyproject.toml` workspace/ruff/pytest settings, remove `_submodule_loader.py` and `git/scripts/_submodule_bootstrap.py`, fix `docs/website/src/constants/submodules.ts`, the lychee excludes, `dependabot.yml`, `AGENTS.md`, `DEVELOPMENT.md`, and the `tools/*/justfile` paths.

## Order of work and owners

1. **Mistral — CRE** (160 files): the smallest, sets the pattern.
2. **Grok — CSG, then HIE** (~820 files together).
3. **Gemini — ASP** (673 files): first absorb the 11 upstream commits (see `absorbed_repos_audit_2026-10-26.md`), then move. Also lands the final PR after the four.
