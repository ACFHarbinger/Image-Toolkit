# AGENT_BUS — Image-Toolkit docs & website migration

**Opened:** 2026-08-10  
**Product lead:** ACFHarbinger (address as Harbinger / ACFHarbinger, not “owner”)  
**Task:** Bring `docs/` + `docs/website` to feature parity with PMF / peer portals; add benchmark ratings dashboard; support human coherence rating pass.

## Role split (proposed — ACK/DISSENT below)

| Agent | Role this sprint |
| --- | --- |
| **Grok** | Benchmark justfile re-wire (done); agent bus; gap analysis; website migration architecture; dashboard metrics pipeline |
| **Chat** | Admin / shared report scaffold; missing `docs/*.md` inventory vs peers; nav/content map |
| **Claude** | React migration design (PMF parity); interactive 2D/3D island plan; code review of site changes |
| **Gemini** | Visual design / hero assets / distinct identity; 3D or simulation island ideas; research links |

## Harbinger concurrent work

- Human coherence ratings via `just asp-benchmark-assess` (now fixed)

## Status log

### grok — 2026-08-10

- Fixed `just asp-benchmark-assess` after ASP → `submodules/ASP` migration.
- Root recipe: `just asp-benchmark-assess` → ASP `eval_dispatch.py` inspector.
- Also re-wired `asp-benchmark*` and triage recipes off broken `uv run` + missing controller path.
- Compatibility shim: `backend/controllers/bench_eval_dispatch.py`.
- Verified: `just asp-benchmark-assess --help` prints full ASP evaluator help.

### (peers append below)

---
