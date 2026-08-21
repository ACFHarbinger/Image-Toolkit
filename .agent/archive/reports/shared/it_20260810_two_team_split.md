# Image-Toolkit — Two-team split (2026-08-10)

**Harbinger:** First-pass human ratings complete for **asp_test01–asp_test18**.

## Team A — Docs & website

**Agents:** Chat, Gemini, Claude (React design lead)

**Work:**

- React rewrite of `docs/website` (full, per Harbinger) without wiping mid-flight data
- Hero asset + visual identity
- Ratings dashboard consumption of `public/data/*`
- Missing docs polish, mkdocs/nav

**Data refresh (any agent):**

```bash
just dashboard-data
# or: node docs/website/scripts/generate-dashboard-data.mjs
```

## Team B — ASP investigation

**Agents:** Grok (initial report), Claude welcome for code deep-dives

**Deliverable (posted):**

`.agent/reports/grok/asp_investigation_tests01_18_20260810.md`

**Headline:** Simple preferred 14/18, mean ASP 2.0 vs Simple 3.39; fallback missed worst cases; sharpness misleads.

## Coordination

`.agent/cache/AGENT_BUS.md` — append-only status.
