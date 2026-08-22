# Handoff — 2026-08-22, pivot from Build-Optimization + `just python` venv fix

Temporary handoff for a fresh Claude session (or this session after a
context reset) picking up Image-Toolkit. Same account, same "coordinator
across several repos" role described in Build-Optimization's own
`.agent/cache/HANDOFF_*` files — this one is Image-Toolkit-specific.
Read this first, then dip into the bus/roadmap files it points at as
needed rather than re-reading full history up front.

## 0. Why you're reading this now — Claude restarting mid-session

Harbinger is restarting Claude Code (an update, not a crash) right after
this session fixed both bugs in §3/§3b below. **Team roster for this
session, as told directly by Harbinger**: Claude, Codex, Agy (Gemini),
opencode — no Grok this round, don't assume that's permanent, rosters
here shift day to day (see the 2026-08-20 handoff's own roster caveat).

Everything below was written *before* the restart, in the same session
that did the work — nothing here is secondhand. A same-day bus entry
covering the same ground was also posted: `.agent/bus/2026-08-22.md`.
Read that too if Codex/Agy/opencode have replied on it by the time you
pick this up — this file won't reflect their responses.

**The one open loop from this session**: nobody has confirmed the actual
GUI works end-to-end. This session's shell has no display — `import
PySide6` and a direct `base.database.Database(...)` construction both
verified clean, but that's not the same as the window opening or the
Database tab's listings actually loading/saving. If Harbinger reports
back that `just python` works (or doesn't), that supersedes this file.

## 1. The workflow this account follows here (same pattern as the other repos)

Image-Toolkit is coordinated by a multi-agent team working async via a
**dated bus log**, not a live shared session — same convention as
Build-Optimization and Online-Price-Comparator (`.agent/bus/AGENT_BUS.md`
in each). Protocol, verbatim from the last real session
(`.agent/cache/HANDOFF_2026-08-20.md`): **propose → cross-review →
Harbinger signs off → build.**

- **Bus index**: `.agent/bus/AGENT_BUS.md` — just a day-pointer table
  here (unlike Build-Optimization's copy, no house rules embedded in it
  directly). Current day file is whatever's newest under `.agent/bus/`;
  everything older moves to `.agent/archive/bus/<date>.md` once the day
  turns over — check the index table for the exact current filename,
  don't assume `2026-08-20.md` is still "today" by the time you read this.
- **Team roster is not static** — as of 2026-08-20: Claude, Codex, Gemini,
  Grok active; deepseek/opencode were off-roster (usage-based,
  re-enabled/disabled by Harbinger over time). **Re-check who's actually
  available before delegating**, don't assume the 2026-08-20 roster still
  holds.
- **House rule**: terse comments/commits/docs, no emoji.
- **Verify-before-trust discipline** (same as every repo this account
  coordinates): never take a bus claim, roadmap status marker, or issue
  state at face value — run the actual command yourself before closing
  anything or building on top of it.
- Full stack/module map: `.agent/AGENTS.md` (mission, tech stack,
  per-module playbooks for `base/`, `backend/`, `gui/`, `frontend/`,
  `app/`, `extension/`, etc.). `CLAUDE.md`/`GEMINI.md` are just pointers
  into it.
- This is a much larger, more mature repo than Build-Optimization: git
  submodules `submodules/ASP` (Anime Stitch Pipeline), `submodules/CSG`,
  `submodules/HIE`, `submodules/CRE`, each with their **own** justfile,
  docs, and sometimes their own `.agent/` — a bus post or roadmap change
  inside a submodule is a separate commit/push target from the root repo.

## 2. Repo state as of the last real work session (2026-08-20)

Nothing coordinated happened between then and this pivot except automated
Dependabot merges (`git log` shows PR merges up to today, no new agent
work). Condensed from `.agent/cache/HANDOFF_2026-08-20.md` — read that
file directly for full detail, this is the short version:

- **ASP issue #30** (full 97-case Raw ASP corpus baseline) — done, closed,
  frozen as the M2+ baseline.
- **ASP #31** (M2 policy cleanup) — verified, but **two decisions are
  blocked on Harbinger, not further agent work**:
  1. The locked M2 exit criterion ("Safe ASP must pick Raw ASP on ≥1
     known-good case AND SCANS on every known catastrophe") may be
     infeasible as specified — a full threshold sweep across all three
     existing gates found zero `(floor, ratio)` combos satisfying it
     simultaneously. Needs a real decision: relax the criterion, invest in
     a new structural signal (open research), or something else.
  2. `CompositeGate` is close to dead weight (`sb` inverse-correlated with
     human judgment, `sc` has no significant signal) — Grok recommended
     redesign/retirement, pending sign-off.
  Full detail: `submodules/ASP/docs/moon/asp_change_roadmap_2026q3.md` §5.
- **ASP #33** (M2.5b learned-proxy spike) — built, **verdict: not feasible
  yet** (only 27 labeled true-composite cases, weak correlation, ridge
  regression underperforms baseline). Honest negative result, revisit once
  the SFW corpus (#38-41) adds labeled cases.
- **ASP #34** (M3 coherence_v2 continuation) — landed: extended the
  single-pose compositor's ownership policy with visibility/boundary/
  frame-quality/temporal-consistency factors, fixed a real pre-landing bug
  (a scoring comparison that couldn't discriminate candidates), 14/14 +
  277/277 tests green. **Still `ASP_COHERENCE_V2=1` opt-in only — do not
  flip it to default-on**, that's reserved for Harbinger's human-screen
  decision.
- **Not pushed anywhere** as of 2026-08-20 (check current state before
  assuming this is still true): `submodules/ASP` (6 local commits ahead),
  `~/Repositories/Other/Project-Mobile-Fortress` (1 local commit, a
  `core/`→`game/` rename — a real active project, not scratch, don't push
  without an explicit ask), root Image-Toolkit repo (5 local bus-post
  commits ahead). `~/Repositories/Templates/Godot-Game-Template` was fully
  pushed and in sync.
- **CSG future-work note**: an MCP-server idea (agent tool access to
  Krita/Blender/OpenToonz) was recorded but explicitly not scoped/
  implemented — `submodules/CSG/docs/moon/roadmaps/agent_dcc_tool_access.md`.
- **Thermal caution may or may not still apply**: the prior session ended
  because of a real CPU thermal incident (100°C CRIT) mid-benchmark, fixed
  by installing a new cooler. **Ask Harbinger directly whether the
  moderate-parallelism caution still applies** before running anything
  CPU-heavy (e.g. ASP benchmarks) — don't infer from silence either way.

## 3. This session: `just python` fixed (root cause, not a workaround)

Harbinger's reported error:
```
just helper::python
source .venv/bin/activate && python backend/main.py
bash: line 1: python: command not found
```

**Root cause, confirmed by direct inspection**: the repo was moved at
some point from `~/Repositories/Image-Toolkit` to
`~/Repositories/Repo/Image-Toolkit` (matching the `Repo/` reorg visible
across this account's other repos — Build-Optimization,
Online-Price-Comparator, Coding-Assistants all live there too). `.venv`'s
activate scripts (bash/zsh, fish, csh, nu, bat — all of them) had
`VIRTUAL_ENV` hardcoded to the **old** path (`~/Repositories/Image-Toolkit/.venv`,
no `Repo/`), which no longer exists. Sourcing `activate` therefore
prepended a nonexistent directory to `PATH`, so `python` resolved to
nothing — even though `.venv/bin/python` existed and worked fine at its
real, correct path (`.venv/bin/python --version` succeeded directly the
whole time; only the PATH-based lookup after `source activate` was
broken). `.venv/bin/python` itself was also a symlink into a **Snap-
sandboxed VS Code path**
(`~/snap/code/248/.local/share/uv/python/...`) rather than a normal
uv-managed interpreter — a second sign the venv was created inside an
unusual (snap-confined) environment before the repo move, not just
stale.

**Fix applied**: `rm -rf .venv && uv sync --all-groups --all-packages`
(the same command `just sync` runs) — full recreation, not a path patch,
so it also self-heals any other absolute-path leakage (editable-install
records, etc.) a `sed` on the activate scripts alone would have missed.

**Verified**:
- `grep VIRTUAL_ENV .venv/bin/activate` → now correctly
  `/home/pkhunter/Repositories/Repo/Image-Toolkit/.venv`.
- `source .venv/bin/activate && command -v python && python --version` →
  resolves to `.venv/bin/python`, `Python 3.11.14` (matches
  `.python-version`).
- `python -c "import PySide6; from PySide6 import QtCore; print(QtCore.__version__)"`
  → `6.10.0`, imports cleanly.

**Not verified — needs Harbinger**: actually launching the GUI event loop
(`just python` end-to-end). This session's shell has no display, so the
import check above is as far as it can go from here. Ask Harbinger to
re-run `just python` on his machine and confirm the window actually opens
before considering this fully closed.

**Housekeeping note, not part of this fix**: `git status` showed
`uv.lock` modified *before* this session touched anything (pre-existing
drift — a new `desktop-quality`/`rerun-sdk` extra plus refreshed wheel
hashes upstream, `uv sync` picked it up). Left as-is, not folded into any
commit for the venv fix — flag it, don't silently absorb someone else's
in-progress lockfile change.

## 3b. Follow-on bug found once `just python` actually ran: `base` extension was never built

Once the venv fix (§3) let `python backend/main.py` actually start, Harbinger
hit a second, deeper bug on first real use: opening the unified library
database failed with `module 'base' has no attribute 'database'` — a
confusing message that isn't what it looks like.

**Root cause #1 — silent namespace-package shadowing, not a missing
import.** `base` is a compiled pybind11 C++ extension
(`base/src/bindings.cpp`, `PYBIND11_MODULE(base, m)`, exposing
`base.database.Database` etc.) that had **never been built** — no
`build/base/`, no `base.cpython-*.so` anywhere. `backend/src/database/unified/session.py`
does `import base  # deferred: keep module importable without the
extension`, expecting a bare `ImportError` if unbuilt. But the repo root
`base/` directory (CMake/C++ source, no `__init__.py`) sits on `sys.path`
(via cwd, since `python backend/main.py` runs from repo root) — Python's
PEP 420 implicit-namespace-package resolution silently "succeeds" on
`import base`, returning an empty namespace object with no `database`
attribute, instead of raising ImportError. That's why the error read as
an `AttributeError`-shaped message rather than "extension not built."

**Fix, part 1**: `pixi install` (fetches the pinned OpenCV 4.13/Eigen3
conda packages `pixi.toml` already declares — not a from-source OpenCV
build, that's a separate unused `build-opencv` justfile recipe) then
`just build-base` (CMake+pybind11 compile of `base/`, ~65 source files,
seconds-scale). Once `base.cpython-311-x86_64-linux-gnu.so` lands at repo
root, it wins over the namespace-package resolution automatically (a real
file match beats a bare-directory namespace candidate in CPython's
import algorithm) — no code change needed, `import base` now resolves to
the real extension.

**Root cause #2 — SQLCipher was genuinely not installed.** Even with the
extension built, constructing `base.database.Database(...)` raised a
second, *intentional* error from the C++ side: `"base was built without
SQLCipher/libsodium. Rebuild with both available."` `HAVE_SQLCIPHER` is a
single compile flag requiring **both** SQLCipher and libsodium found at
CMake-configure time, or the whole encrypted-DB layer (`base/src/database/database.cpp`,
`base/src/secret/vault_db.cpp`, `base/src/utils/migration.cpp`) compiles
as a stub that raises on every call, by design (a deliberate "never
silently degrade the encrypted store" choice, not a bug). libsodium was
already available via the pixi env; **SQLCipher was not** —
`libsqlcipher-dev` is in Ubuntu's `universe` repo but wasn't installed.

**Fix, part 2** (Harbinger installed it directly, `sudo apt install
libsqlcipher-dev` — a system-wide/sudo change, correctly not something
this session did unilaterally without asking first): re-ran `just
build-base`. `build/base/CMakeFiles/base.dir/flags.make` now shows
`-DHAVE_SQLCIPHER=1`, and a live smoke test —
`base.database.Database(tmp_path, "testpass", "testsalt")` — constructed
and closed successfully (previously raised `TypeError`).

**Still not verified**: the actual GUI end-to-end (this session's shell
has no display, same limitation as §3). Ask Harbinger to confirm `just
python` now opens the window *and* that the Database tab's listings
actually load/save, not just that construction no longer throws.

**Worth remembering for next time a `base`-adjacent error looks like a
missing-attribute rather than an import failure**: check whether `base/`
(source dir, no `__init__.py`) is shadowing the compiled `.so` via
namespace-package resolution before assuming the extension itself is
broken — `python -c "import base; print(base.__file__)"` immediately
tells you which one you got (`None` = namespace-package shadow, a real
path ending `.so` = the actual extension).

## 4. Not yet started / no owner

Same as 2026-08-20, still true as far as this session can tell:

- The two Harbinger-blocked M2 decisions (§2 above).
- M3's next step (promotion vs. further ownership-policy iteration) —
  blocked on Harbinger's human-screen call on `ASP_COHERENCE_V2`.
- M4 (motion-compensated hold/selection, ASP issue #35) — not started,
  next in the roadmap's locked ordering after M3's human screen.
