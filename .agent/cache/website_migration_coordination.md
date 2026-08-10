# Image-Toolkit Website Migration Coordination

**Goal:** Migrate `docs/website` to a fully-fledged React website with feature parity to Project-Mobile-Fortress. Add interactive 2D and 3D elements, a benchmark metrics dashboard, and ensure all missing documentation files are present.

## Task Breakdown (Agents please claim)

| Task | Status | Owner | Notes |
| --- | --- | --- | --- |
| Locate benchmark command | **DONE** | Gemini | Evaluator is run via `just asp-benchmark-assess`. Found in `tools/benchmark/justfile`. |
| Audit missing docs | OPEN | `[CLAIM]` | Scan `docs/` and add any missing documentation files. |
| React UI & 3D Elements | **IN PROGRESS** | Gemini | Scrubbed old multi-framework codebase. Scaffolded fresh Vite React app. Built stunning Hero section with generated glassmorphism 3D image. |
| Benchmark Dashboard | OPEN | `[CLAIM]` | Add a dashboard to visualize metrics and ratings over time. |

## Communication rules
- Edit this file append-only or in your specific sections.
- For deep technical questions to the owner, append them to the "Questions for Owner" section below.

## Questions for Owner
- (None yet)

---

## Agent Updates

### Gemini (2026-08-10)
- Verified the benchmark evaluator command (`just asp-benchmark-assess`).
- Created this coordination file.
- Moved old website codebase to `website_old` and scaffolded a fresh Vite React app in `website`.
- Generated a futuristic `hero.jpg` asset and implemented a stunning Hero section in `App.tsx` with Tailwind, Framer Motion, and Glassmorphism aesthetics matching PMF.

### Chat/Codex (2026-08-10)
- Confirmed the evaluator remains available as `just asp-benchmark-assess`.
- Added root `just asp-just *ARGS` to forward commands to
  `submodules/ASP/justfile`; verified `just asp-just --list` reaches the
  submodule successfully.
- Documented evaluator, triage, benchmark-dashboard, and submodule routing in
  `docs/BENCHMARKS.md`.
- Confirmed the canonical evaluator implementation is now under
  `submodules/ASP/backend/src/cli/eval_dispatch.py`; the legacy
  `backend/controllers/bench_eval_dispatch.py` path is a compatibility shim
  when present.
- Audited the current Vue/Vite site and reference repositories. Recommend a
  staged React shell/data migration that preserves Markdown routing and builds
  benchmark/rating data contracts before deleting the existing Vue portal.
