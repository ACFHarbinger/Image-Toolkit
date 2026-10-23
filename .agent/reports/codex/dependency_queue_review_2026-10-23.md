# Dependency queue review — 2026-10-23

Reviewed all twelve open PRs. Eight have no dependency-specific blocker; four remain on hold or require changes. #937 is already closed. No PR was merged. All twelve were MERGEABLE when inspected; no rebase is presently required just to resolve Git conflicts.

| PR | Reviewed head | Disposition | Evidence / next action |
| --- | --- | --- | --- |
| #813 | `16b43b052` | No dependency blocker | rustls/webpki patch updates only. Cargo metadata --offline --locked --no-deps passes; recorded CI checks pass. No fresh Rust compile. |
| #814 | `24d1dcf27` | No dependency blocker | Next and matching SWC/env packages update together; workspace manifest and lock entry agree. Recorded docs typecheck/build passes. Failed lychee links are external403/429; preview deploy lacks credentials. |
| #815 | `503d304a8` | No dependency blocker | KaTeX manifest/lock update agree; recorded docs typecheck/build passes. Failed lychee links are external403/429; preview deploy lacks credentials. |
| #816 | `f10d98f51` | No dependency blocker | PostCSS manifest/lock update agree, including nanoid dependency range. Recorded docs typecheck/build passes. Failed lychee links are external403/429; preview deploy lacks credentials. |
| #820 | `99598ef73` | No dependency blocker | Tauri/plugin, Tokio, UUID and serde_json changes remain within existing manifest ranges. Cargo metadata --offline --locked --no-deps passes. Recorded functional/build checks pass; slow Python job was cancelled. No fresh Rust compile. |
| #823 | `4739ceb0c` | No dependency blocker | pixi lock --check --dry-run --no-config passes. Reviewed Linux/Windows package records: rebuilds and native patch/minor changes, channels/platforms preserved; no Torch version change. Failed import-linter traces an existing GUI dependency path, not changed by this lock-only diff. No fresh native environment installation. |
| #923 | `58a5f946e` | Hold: refresh stale lock | aiohttp3.14.4 and yarl1.25.1 diff has no identified API defect, but uv lock --check --offline fails at both head and merge-base with uv0.13.1. Refresh against current manifests and recheck before landing; do not attribute pre-existing staleness to this bump. |
| #925 | `bbcdc5edd` | Changes required | Four docs sites upgrade Tailwind3 to4 but retain plugins:{tailwindcss:{}} and @tailwind directives. v4 moves the PostCSS plugin to @tailwindcss/postcss and replaces directives with an import. Migrate configuration/CSS or split out the Tailwind major bump. Existing frontend CI also fails npm ci with root Vite manifest/lock mismatch; that root file is outside this diff. Changed package manifests and local lock entries agree, but this does not validate runtime compatibility. |
| #927 | `be5836dc4` | Hold: subproject runtime validation | ASP uv lock --check --offline passes. Group also changes torch2.13.0 to2.14.1, torchvision0.28.0 to0.29.1, CUDA libraries and Triton3.8.0, beyond named direct bumps. Root CI syncs root workspace rather than this subproject lock. Need bounded ASP import/operator checks in this exact resolved environment before clearing runtime compatibility. Do not install GPU stack into shared venv. Coordinate with overlapping #940 rather than merging two independently resolved ASP locks. |
| #938 | `e91167f67` | No dependency blocker | uv0.12.5 to0.13.4 only substantive package change. uv lock --check --offline passes using installed uv0.13.1; recorded CI passes. Updated uv0.13.4 executable itself was not installed/run locally. |
| #939 | `e0e8f3912` | No dependency blocker | certifi update only substantive package change; registry sources/hashes retained in lock structure. uv lock --check --offline and recorded CI pass. No live TLS endpoint smoke. |
| #940 | `c6878a2d8` | Hold: subproject runtime validation | Both ASP and HIE uv lock --check --offline pass. ASP updates Torch/torchvision/CUDA/Triton; both projects upgrade Pillow12 to13; HIE introduces Gymnasium/cloudpickle/farama-notifications. Need bounded image/ML compatibility checks using these subproject locks, which root CI does not sync. Coordinate ASP changes with #927; preserve its Lightning bump if consolidating, since #940 does not include it. |

## Check scope

Fresh checks used isolated manifest/source snapshots under `~/Downloads/Data/Tests/dependency-review-2026-10-23/`, preserving shared checkout changes. Parsed changed TOML/JSON/YAML locks, compared package changes to actual merge bases, checked each changed npm manifest against its corresponding lock entry, checked both Rust workspace metadata graphs, ran six uv lock checks (five passed; #923 failed), repeated #923 against its base (same failure), and checked Pixi without installation (passed).

Existing GitHub CI results are historical evidence, not newly run suites. For #814/#815/#816, inspected each failed deployment/link job: missing deploy token and external403/429 links. #823's failed job records GUI import-boundary violation; no Python source changes in that PR. #925's failed frontend job records npm ci root Vite mismatch, separate from the newly identified Tailwind integration defect.

No dependency installation, fresh native build, test suite, GPU training, benchmark, Windows execution or live TLS operation was performed. No claim of complete runtime compatibility for #927/#940. No package manifest/source code edited.

## Claude handoff

Land acceptable changes serially with required CI/branch policy satisfied; lockfiles overlap, so regenerate/recheck after earlier landings. The review disposition is not a CI override. Refresh #923; return #925 for Tailwind integration; coordinate #927/#940 into a consistent ASP update and obtain subproject checks. #937 is closed and removed from the landing queue.

Tailwind v4 migration requirements: [official upgrade guide](https://tailwindcss.com/docs/upgrade-guide#using-postcss).
