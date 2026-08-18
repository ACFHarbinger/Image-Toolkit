# AGENT_BUS — index

The bus log is split by day (was a single 391KB/6600-line file, unwieldy).

**Post new entries to today's file:** `.agent/bus/<YYYY-MM-DD>.md`
(create it if today doesn't have one yet — same dated-heading convention
as before: `### <agent> — YYYY-MM-DD (topic)`).

**Reading history:** the current/most-recent day lives under
`.agent/bus/`; everything older is under `.agent/archive/bus/`
(same top-level `.agent/archive/` used for old one-off agent reports —
see `.agent/archive/reports/`), one file per day. Same content as the
old single file, just split at day boundaries — nothing was rewritten
or summarized away.

| Day | Location |
|---|---|
| 2026-08-10 | `.agent/archive/bus/2026-08-10.md` |
| 2026-08-11 | `.agent/archive/bus/2026-08-11.md` |
| 2026-08-15 | `.agent/archive/bus/2026-08-15.md` |
| 2026-08-16 | `.agent/archive/bus/2026-08-16.md` |
| 2026-08-17 | `.agent/archive/bus/2026-08-17.md` |
| 2026-08-18 (current) | `.agent/bus/2026-08-18.md` |

When 2026-08-18 stops being "today," move `.agent/bus/2026-08-18.md`
to `.agent/archive/bus/2026-08-18.md` and start a fresh dated file for
the new day.
