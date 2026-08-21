# Image-Toolkit Documentation and Website Review

**Author:** Chat/Codex  
**Date:** 2026-08-10  
**Status:** Initial discovery

## Executive assessment

Image-Toolkit already has unusually broad documentation infrastructure: MkDocs
as the content/nav source, a Vue/Vite documentation SPA, TypeDoc generation,
Astro/React/Aurelia islands, Storybook, Mermaid support, notebooks, and a
Streamlit benchmark dashboard. The weakness is not a lack of technology; it is
that these surfaces are not yet unified into one deliberate product experience.
The migration should therefore be staged around a stable content/data contract,
not a destructive framework rewrite.

## Current website findings

- `docs/website/` is currently Vue 3 + Vite, despite containing React and other
  framework islands.
- `HomeView.vue` is an engineering hub with module, ecosystem, roadmap, and
  framework-island tabs. It is a useful shell but not yet a visually distinctive
  product landing page or analytics workspace.
- The site has a generated documentation navigation from `docs/mkdocs.yml` and
  renders Markdown client-side, which should be preserved while the shell and
  interactive panels evolve.
- Existing Astro and Aurelia experiments demonstrate a multi-framework island
  pattern, but the desired next state needs a clear primary UI architecture,
  shared design tokens, responsive behavior, reduced-motion support, and
  testable data visualizations.

## Benchmark/evaluator finding

The evaluator command was not removed:

```bash
just asp-benchmark-assess
```

The current benchmark routing delegates through `tools/benchmark/justfile` to
the ASP submodule's canonical dispatcher:

```bash
uv run python submodules/ASP/backend/src/cli/eval_dispatch.py
```

The compatibility path `backend/controllers/bench_eval_dispatch.py`, when
present, forwards to the same submodule implementation for older callers.

Other existing commands include `just benchmark-save`,
`just benchmark-dashboard`, `just asp-benchmark`, and `just asp-triage`.
The ASP submodule also has its own root Justfile at
`submodules/ASP/justfile`, with benchmark module commands under `just bench::*`.

The root repository now provides `just asp-just ...` as a documented,
non-ambiguous wrapper for launching the ASP submodule's root Justfile without
changing the existing evaluator aliases.

## Recommended implementation sequence

### Updated direction

The later coordination decision is a **full Vue-to-React rewrite**, not a
staged compatibility migration. The preservation requirement still applies to
content behavior—Markdown routing, search, navigation, deep links, and deploy
must retain parity—but temporary Vue adapter infrastructure should not be
added. React is the primary site runtime from the first migration slice.

1. Define a versioned benchmark snapshot schema covering run metadata, suite,
   comparator, dataset/test ID, automated metrics, human rating dimensions,
   confidence, defects, and provenance.
2. Add a generated/static data adapter consumed by both the website dashboard
   and any existing Streamlit/Markdown reporting.
3. Establish the visual system and React route/component boundary in parallel,
   retaining the current Markdown route until parity is proven.
4. Add benchmark history, ratings-over-time, metric-vs-human agreement, and
   run/telemetry views with explicit empty/missing/error states.
5. Add 2D DAG/network visualization first, then a lazy-loaded 3D scene with a
   2D fallback, reduced-motion mode, and a performance budget.
6. Migrate documentation pages and nav/build/deploy wiring incrementally.
7. Run accessibility, type, unit, visual, production-build, and link checks.

## Guardrails

- Do not claim feature parity merely by copying dependencies or framework
  directories; parity means equivalent user-visible workflows and quality.
- Do not copy PMF assets blindly. Record provenance and license status; create a
  distinct Image-Toolkit hero treatment if reuse is not clearly permitted.
- Do not conflate human coherence ratings with SSIM, sharpness, seam, or pose
  metrics. Display them as separate dimensions and show coverage.
- The rewrite may remove the Vue portal as agreed, but each React migration
  slice must restore equivalent Markdown routing, search, navigation, deep
  links, and deployment before it is considered complete.

## Quality finding from the active human rating pass

ACFHarbinger reports that the current ASP output is more coherent than the
pre-refactor baseline but still loses to OpenCV SCANS on almost all reviewed
cases. The visible failure modes are banding, color shifts, and degraded seam
lines, while SCANS generally has only slight ghosting. The dashboard and future
ASP roadmap must preserve this distinction: the current result is evidence to
investigate the algorithm, not a reason to polish away or reinterpret the
quality signal.
