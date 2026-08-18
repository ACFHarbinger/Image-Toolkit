# Image-Toolkit — Docs & Website Migration Kickoff (Grok)

**Date:** 2026-08-10  
**Author:** Grok (Build)  
**Address Harbinger as:** Harbinger / ACFHarbinger  

---

## 1. Coding-Assistants sign-off

Read ACFHarbinger’s final GO on the CA shared report. **Agree.** Planning closed; Plan Alpha cleared. Will use **Harbinger / ACFHarbinger** instead of “owner” going forward.

---

## 2. Human coherence evaluator — how to run it

The root justfile recipe **exists** but was **broken** after ASP moved to `submodules/ASP`:

| Before (broken) | After (fixed) |
| --- | --- |
| `uv run python backend/controllers/bench_eval_dispatch.py` | Direct `.venv` python + ASP path |
| Missing controller file | Real dispatch: `submodules/ASP/backend/src/cli/eval_dispatch.py` |
| `uv` fails on CSG workspace-only pyproject | Avoid bare workspace `uv run` |

### Commands (from Image-Toolkit root)

```bash
# Primary — PySide6 per-test human rating inspector
just asp-benchmark-assess

# Help / options
just asp-benchmark-assess --help

# Useful flags
just asp-benchmark-assess --data-dir dump
just asp-benchmark-assess --start-at asp_test09
just asp-benchmark-assess --redo
just asp-benchmark-assess --theme dark

# Optional FiftyOne corpus triage (needs Mongo + benchmark-eval extra)
just asp-triage-db          # docker mongo on :27017
just asp-triage             # build + open App
just asp-triage-ingest
just asp-triage-sync pull   # or push
```

Also available:

```bash
just asp-benchmark-verify   # 5-test quality suite
just asp-benchmark-first 5
just benchmark-dashboard    # Streamlit IT perf dashboard (not human ratings)
```

**Verified:** `just asp-benchmark-assess --help` returns the full Phase 0.1 evaluator usage text.

**Ratings output:** `data/benchmarks/asp_evaluations_YYYYMMDD.json` (or Settings-configured out dir).

---

## 3. Docs / website current state (gap vs PMF)

| Area | Image-Toolkit today | PMF / target |
| --- | --- | --- |
| Site stack | Vue 3 + Vite primary; also Nuxt/Next/Astro/Storybook mixed | React 19 + Vite primary + Astro islands + Storybook |
| Entry | `src/main.ts` + Vue `App.vue` | `src/main.tsx` + React views |
| Visual identity | Hub CSS present; weaker “hero” identity | Strong hero assets, distinct lore/docs look |
| Docs markdown | ARCHITECTURE, BENCHMARKS, TROUBLESHOOTING, moon, tutorials | Full suite + generated docs-content |
| Missing docs (vs CA/PMF style) | No root-level CHANGELOG/SECURITY/TESTING/DEVELOPMENT/GLOSSARY/TUTORIAL in `docs/` (some live only as readme.md) | Explicit suite |
| Ratings dashboard | Streamlit `benchmark_dashboard.py` for IT perf; **no** time-series human-coherence dashboard on docs site | Need site-native charts for ASP metrics + human ratings over time |

---

## 4. Proposed website migration plan

### Phase A — Foundation (this week)

1. Align `docs/website` on **React + Vite** as primary (PMF parity), keep Vue only if needed as legacy island during transition.  
2. Port/generate nav from mkdocs + moon + tutorials.  
3. Hero / brand assets for Image-Toolkit (distinct from PMF; photography/panorama motif).  
4. Add missing `docs/*.md` stubs or full pages: SECURITY, DEVELOPMENT, TESTING, CHANGELOG, GLOSSARY, CONTRIBUTING links.  
5. **Benchmark Ratings Dashboard** route:
   - Load `data/benchmarks/asp_evaluations_*.json` + `backend/benchmark/results/*.json`
   - Charts: score distributions, ASP vs Simple preference over time, per-test heatmap, defect tags, metric-vs-human disagreement  
   - 2D DAG optional for pipeline stages; 3D later (force-graph of tests/comparators)  

### Phase B — Interactive depth

6. 2D: pipeline stage flow, seam diagnostics, module graph (existing pyvis/module-graph hooks).  
7. 3D: optional force-graph island (research-quality first; not blocking ratings dashboard).  
8. Storybook + Astro island budgets like PMF.  

### Phase C — Content completeness

9. Tutorials gallery polish; ASP critical evaluation + moon roadmaps as first-class pages.  
10. Export dashboard snapshots into `docs/moon/reports/` for git history.

---

## 5. Multi-agent coordination

Use:

- `.agent/cache/AGENT_BUS.md` — live coordination  
- `.agent/reports/{grok,chat,claude,gemini}/` — deep reports  
- `.agent/reports/shared/` — joint synthesis  
- `.agent/reports/admin/` — Harbinger decision report  

Grok owns: assess tooling (done), dashboard metrics schema, migration architecture notes.  
Peers: content map (Chat), React parity design (Claude), visual identity (Gemini).

---

## 6. Immediate next code steps (Grok)

1. ✅ Re-wire `just asp-benchmark-assess`  
2. Scaffold dashboard data loader + route stub on docs website  
3. Add missing docs skeleton files under `docs/`  
4. Commit assess fix + kickoff reports  

---

## 7. Closing

Harbinger can run the rating pass now with:

```bash
cd ~/Repositories/Repos/Image-Toolkit
just asp-benchmark-assess
```

While that runs, agents proceed on docs/website migration and the ratings-over-time dashboard.
