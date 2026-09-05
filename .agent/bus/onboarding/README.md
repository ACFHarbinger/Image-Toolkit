# Onboarding — new agents joining Image-Toolkit's multi-agent workflow

You're joining an existing team of AI coding agents working the same repo
in parallel, coordinated by the user (ACFHarbinger) through a shared
"agent bus." Current roster: Codex, Gemini/Antigravity, Grok, DeepSeek
(opencode), Opencode (mimo), Claude — and the user is actively trialing
more (Cursor, Meta's Muse, and looking into a persistent Perplexity agent
in a TUI) to see which stick as a permanent part of the R&D workflow. If
you're one of these newer arrivals: welcome, and don't assume you're the
only "new" one — check the bus for how recently others joined too.

Read this file in full before touching code or posting.

## 1. Read these two files first, in this order

1. **`AGENTS.md`** (repo root) — the actual operating rules: tech stack,
   CLI entry points, and critically the **RESOURCE RULE** (§3): no agent
   except Codex may run a full test suite or a benchmark/corpus run
   without going through Codex + explicit user go-ahead. Multiple agents
   running these concurrently has crashed the user's machine before. This
   applies to you too, no exceptions. Small/targeted checks (`py_compile`,
   `ruff check`, a single test file) are fine on your own.
2. **`.agent/reports/team/architecture_deep_dive_2026-09-05.md`** — the
   living synthesis/decision record for the team's current main focus
   (see §3 below). This is *not* the raw chronological log — it's the
   "what did we actually decide and why" document. Read all of it,
   especially §5 (Decisions D1-D18) and §7 (the locked roadmap).

## 2. How the bus actually works

- `.agent/bus/<YYYY-MM-DD>.md` is today's append-only log — every agent
  posts dated, signed entries (`### <you> — YYYY-MM-DD (topic)`) at the
  bottom. It's the *narrative*; the report above is the *synthesis*.
  Don't confuse the two — big decisions belong in the report, not just
  buried in a bus post.
- Old days live under `.agent/archive/bus/` once stale; the index is
  `.agent/bus/AGENT_BUS.md`.
- **This repo's working directory is shared** across concurrent agent
  sessions (and separate git worktrees exist per active feature branch —
  check `git worktree list` before assuming you're alone in the tree).
  `git status` before committing; don't blindly `git add -A`. If you need
  to commit a docs/bus change onto a branch other than whatever's
  currently checked out in the shared tree (e.g. landing a post on `main`
  while a feature branch is checked out), use an isolated
  `git worktree add /tmp/<name> <branch>` rather than switching branches
  in the shared directory — switching can fail or collide with another
  session's live edits.
- The user runs each agent in its own session and relays cross-agent
  decisions manually sometimes — so if you see a decision recorded that
  references "confirmed in [some other agent]'s session," that's real,
  not a hallucination; the user is the actual routing layer between
  sessions when agents can't otherwise talk to each other directly.

## 3. What's actually going on right now

A same-day GUI/UX aesthetics update (~108 commits) caused a real startup
crash (`QSocketNotifier` cross-thread violation → SIGSEGV) and surfaced a
disproportionate number of real bugs for what should've been cosmetic
work. It was **fully reverted** (`gui/` restored to `b4f61deb`). That
whole saga is archived at
`.agent/archive/bus/2026-09-05-pre-revert.md` — read it only if you want
the war story; it's not live code anymore.

That crash is why the team is now doing a **structural architecture
deep-dive and refactor** — re-organizing project layout, building
genuinely reusable/modular components, fixing bugs found along the way,
and chasing optimization gains. This is the team's **main focus right
now** (the user explicitly deprioritized other in-flight work, like the
v1.0.0 release blockers, in favor of this).

**Where it stands (decisions D1-D18 locked; check the report/bus for
anything more recent than this snapshot):**

- **Phase 0 — invariant lock** (blocking gate; nothing in Phase 1 starts
  until this lands and passes a live-desktop smoke test, not just
  offscreen CI): serialize native-decode + GIF bypass, visible-first
  thumbnail dispatch on all four gallery implementations, one-owner
  preferences (tray setting as the proof case), quarantine unwired
  prototype UI code into `gui/src/protos/`. **As of the last check, none
  of Phase 0's four sub-issues has actually landed on `main` yet** —
  they're on review-pending feature branches, and #522 (visible-first
  dispatch) specifically has an open blocker (see the bus for Codex's
  review). Don't assume Phase 0 is done just because pieces say
  "implementation complete" — check whether it's merged and reviewed.
- **Phase 1 — six parallel contract epics** (blocked on Phase 0):
  `PreferenceStore`, `ThumbnailScheduler` interface,
  `ModuleDescriptor`+`ModuleHost` pilot, `WindowManager`, backend
  Qt-decoupling (`Observable` primitive), CI import-boundary guardrails.
- **Phase 2/3** (consolidation, then optimization) — deferred, lighter
  detail, tracked but not started.

**GitHub tracking:** milestone
["Architecture Deep-Dive (2026 Q3)"](https://github.com/ACFHarbinger/Image-Toolkit/milestone/9),
issues **#520-#532**. Full owner table is report §6 — every item
currently has an owner. If you want to pick up work, the honest options
are: wait for someone to finish and hand off a piece, help review/verify
someone else's Phase 0 work (genuinely useful right now — see the #522
blocker above), or propose a genuinely new piece of scope the team hasn't
covered — post it to the bus and the report's Q&A section (§4) rather
than just starting.

## 4. Process lessons already learned this round — please don't repeat them

1. **Independent analysis converged into near-duplicate questions.**
   Several agents asked the user largely the same questions (Phase 0
   shape, ownership, exit criteria) with cosmetic wording differences
   across separate sessions, forcing repeated answers. Before you ask the
   user something, check §4 of the report and the bus — if it's already
   been asked (even in different words), build on/challenge the existing
   answer rather than re-deriving it fresh.
2. **Implementation started before the roadmap left DRAFT status.** One
   agent began landing code before the team's roadmap was locked. It was
   contained (isolated branch, sound content) but the expected order is
   **claim on the bus → wait for the relevant phase gate → then code**,
   not the reverse. The roadmap is locked now (§7 status: LOCKED), but
   the general principle still stands, especially given this week's
   crash history: claim before you code, especially anything touching
   gallery loading, threading, or startup/preference paths.
3. **"Implementation complete" isn't the same as "landed."** Several
   Phase 0 pieces were posted as done but hadn't been reviewed or merged,
   and one (#522) turned out to have a real correctness blocker on
   review. Don't treat a bus post claiming completion as ground truth for
   what's actually safe to build on — check whether it merged, and
   whether review actually happened.

## 5. If you want to contribute right now

- Check the bus for the latest status on #520-#532 before assuming a
  piece is idle or done — ownership and status change fast, faster than
  any snapshot in this file.
- Reviewing someone else's Phase 0 branch is genuinely useful work if you
  don't have (or don't want) a piece of your own yet.
- If you find something the analysis passes missed, or want to challenge
  a locked decision (D1-D18 in report §5) with new evidence, post it —
  decisions aren't sacred, they're just the current best answer; a good
  counter-argument is welcome, re-litigating without new information
  isn't.
- Sign every bus post and every report edit with your name and date.
  Append, don't rewrite others' sections in the report (it's explicitly a
  living/shared document, not yours to restructure solo).

Welcome aboard.

— Claude, 2026-09-05
