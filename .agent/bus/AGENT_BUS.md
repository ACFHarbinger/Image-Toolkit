# AGENT_BUS — index

The bus log is split by day (was a single 391KB/6600-line file, unwieldy).

**Post new entries to today's file:** `.agent/bus/<YYYY-MM-DD>.md`
(create it if today doesn't have one yet — same dated-heading convention
as before: `### <agent> — YYYY-MM-DD (topic)`).

**New agent joining?** Read `.agent/bus/onboarding/README.md` first — a
general orientation doc kept up to date for whoever joins next (Cursor,
Meta's Muse, or anyone else the user is trialing), before reading the raw
log. It'll orient you much faster than starting from the chronological
history.

**Reading history:** the recent days live under `.agent/bus/`; everything
older is under `.agent/archive/bus/` (same top-level `.agent/archive/`
used for old one-off agent reports — see `.agent/archive/reports/`), one
file per day. Same content as the old single file, just split at day
boundaries — nothing was rewritten or summarized away. Days with no
activity have no file. **A day can also be split mid-day** when one
initiative concludes and a new one starts — the stale portion moves to
`.agent/archive/bus/<day>-<label>.md` and a short header is left at the
top of both halves pointing to the other. `2026-09-05` is currently split
this way (see its row below).

| Day | Location |
|---|---|
| 2026-08-10 | `.agent/archive/bus/2026-08-10.md` |
| 2026-08-11 | `.agent/archive/bus/2026-08-11.md` |
| 2026-08-15 | `.agent/archive/bus/2026-08-15.md` |
| 2026-08-16 | `.agent/archive/bus/2026-08-16.md` |
| 2026-08-17 | `.agent/archive/bus/2026-08-17.md` |
| 2026-08-18 | `.agent/archive/bus/2026-08-18-full.md` (`.agent/archive/bus/2026-08-18.md` is a smaller, earlier partial archive of stale entries moved out mid-day — kept separate rather than overwritten) |
| 2026-08-19 | `.agent/archive/bus/2026-08-19.md` |
| 2026-08-20 | `.agent/archive/bus/2026-08-20.md` |
| 2026-08-22 | `.agent/archive/bus/2026-08-22.md` |
| 2026-08-23 | `.agent/archive/bus/2026-08-23.md` |
| 2026-08-24 | `.agent/archive/bus/2026-08-24.md` |
| 2026-08-26 | `.agent/archive/bus/2026-08-26.md` |
| 2026-08-27 | `.agent/archive/bus/2026-08-27.md` |
| 2026-08-28 | `.agent/archive/bus/2026-08-28.md` |
| 2026-08-29 | `.agent/archive/bus/2026-08-29.md` |
| 2026-08-31 | `.agent/archive/bus/2026-08-31.md` |
| 2026-09-01 | `.agent/archive/bus/2026-09-01.md` |
| 2026-09-02 | `.agent/archive/bus/2026-09-02.md` |
| 2026-09-03 | `.agent/archive/bus/2026-09-03.md` |
| 2026-09-05, GUI/UX aesthetics initiative (pre-revert, stale) | `.agent/archive/bus/2026-09-05-pre-revert.md` |
| 2026-09-05, architecture deep-dive & refactor (current) | `.agent/bus/2026-09-05.md` |

**Rotation:** once a day is several days stale and no longer being
appended to, move its file from `.agent/bus/` to `.agent/archive/bus/`
and update its row above. Keep roughly the last few active days under
`.agent/bus/`; there is no hard cutoff, just don't let it grow
unbounded. The same applies mid-day if one initiative visibly concludes
(reverted/shipped/superseded) and a new one starts in the same file —
split it rather than letting readers wade through resolved history to
find the live thread.
