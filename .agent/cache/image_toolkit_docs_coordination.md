# Image-Toolkit Documentation and Website Migration Coordination

**Created:** 2026-08-10  
**Coordinator:** Chat/Codex  
**Status:** Discovery complete; implementation tracks ready

## Shared objective

Bring `docs/` and `docs/website/` to a coherent, fully featured documentation
and analysis experience. Preserve the existing documentation portal while
moving the public site toward a React-first architecture with polished visual
identity, interactive 2D/3D technical visualizations, benchmark history, human
coherence ratings, and telemetry dashboards. Use the existing repository
content and the proven patterns/assets from Project-Mobile-Fortress,
Organization-Website, and Visual-Graph-Programming where licensing and
provenance permit.

## Tracks

| Track | Scope | Lead/status |
| --- | --- | --- |
| A | Root/ASP Justfile entry point, evaluator command documentation, benchmark data contract | Chat — active |
| B | Website framework migration and visual system parity | To be assigned by shared agent coordination |
| C | 2D/3D graph and dashboard components | To be assigned by shared agent coordination |
| D | Documentation inventory, missing pages, nav/build/deploy parity | To be assigned by shared agent coordination |
| E | Assets/provenance, accessibility, performance, visual QA | To be assigned by shared agent coordination |

## Confirmed discovery

- Root `justfile` currently exposes `just asp-benchmark-assess`, which delegates
  to `tools/benchmark/justfile` and then to
  `backend/controllers/bench_eval_dispatch.py`.
- Root also exposes `just benchmark-dashboard`, `just benchmark-save`, and the
  ASP benchmark variants. The ASP submodule has its own root Justfile under
  `submodules/ASP/justfile` and its own `just bench::*` module.
- The current docs site is a Vue 3 + Vite SPA with Astro, React, and Aurelia
  islands. It has no first-class benchmark-history dashboard in the site.
- Existing benchmark surfaces include the Streamlit dashboard,
  `backend/benchmark/run_all.py`, ASP JSON output, the PySide6 evaluator, and
  FiftyOne triage/sync. Human structural-coherence ratings remain a human
  input, not an automated metric.
- Reference repositories are available at:
  `/home/pkhunter/Repositories/Other/Project-Mobile-Fortress`,
  `/home/pkhunter/Repositories/Other/Organization-Website`, and
  `/home/pkhunter/Repositories/Other/Visual-Graph-Programming`.

## Coordination rules

- Agents write only to `.agent/reports/{agent}/` and shared coordination/report
  files unless a task explicitly assigns source changes.
- Do not copy generated `dist/`, `.next/`, `node_modules/`, or private data.
- Every imported visual asset must have a source/provenance note and a license
  check before publication.
- Benchmark visualizations must distinguish measured metrics from human ratings,
  show missing data explicitly, and never imply that a proxy metric equals
  human coherence.
- Keep the current docs portal buildable during the migration; use an adapter
  or staged route migration rather than deleting the working portal first.

## Open decisions for the joint brainstorm

1. React-only replacement versus a staged Vue-to-React route migration.
2. Three.js/react-three-fiber versus a lighter WebGL/canvas layer for graphs.
3. Static checked-in benchmark snapshots versus a generated data pipeline.
4. Whether the public site should ship the PMF hero image itself or use a
   newly generated Image-Toolkit-specific hero asset inspired by its visual
   treatment.
5. Whether dashboard data should be loaded from repository JSON only or later
   from a local/API endpoint.
