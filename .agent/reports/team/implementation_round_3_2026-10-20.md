# Implementation round 3 — 2026-10-20

— Claude, coordinator. Harbinger has restored the roles: **Claude oversees**
(GitHub upkeep, delegation and landing), **Codex reviews and makes final
edits**, and **Grok develops**. This supersedes the role split in the
2026-10-19 handover and in round 2.

## Roles and flow

- **Landing order:** author → **Codex review and final edits** on the
  author's branch → **Claude lands.**
  - Squash merges, except history imports, which need a merge commit.
  - CI is judged against main's baseline. Only lychee fails on main, on two
    external links.
- **RESOURCE RULE, unchanged:** only Codex runs full suites and benchmarks,
  with Harbinger's go-ahead per run. Targeted checks are open to everyone.
- **Spikes:** S-01…S-07 each need a written go/no-go note.
  **Harbinger decides on Codex's review.** A no-go keeps that PySide6 row
  alive past its wave.
- **Work in your own worktree or branch.** Never `git stash` in the shared
  checkout. Stage only your own paths. Coordinate `package.json`/lockfile
  edits on the bus first.

## Landed since round 2 (Claude, 2026-10-20)

| PR | Issue | Commit | Note |
|---|---|---|---|
| #931 | #874 contracts | `2ff5f3222` | |
| #929 | #877 supervisor | `12d362e32` | `request_focus` caller comes in #873 |
| #932 | #869 catalog | `eafb53da2` | |
| #930 | #868 Vite/security | `d1da3575a` | Claude merged main in to resolve a `ci.yml` keep-both conflict with #931 |
| #935 | #879 follow-up | `6763b6021` | #879 stays open for supervisor-enforced binding |
| #933 | #884 guardrails | pending | Claude merged main in to resolve an AGENTS.md conflict with #930; lands on green CI |

## Finish first (carry-over)

| Agent | Item | What's left |
|---|---|---|
| **Mistral** | #875 bridge (`tauri/w0-11-bridge`) | #931 is on main. Rebase onto main keeping Codex's `6d69b0e16`, re-verify, open the PR. |
| **Kimi** | #878 EventHub (`tauri/w0-14-eventhub`) | #930 and #931 are on main. Rebase keeping Codex's `b4f6401ca`, re-verify against #875, open the PR. |
| **Cursor** | #873 tray / window roles (PR #934) | **It conflicts with main.** Rebase on #930. OS checklist for Harbinger. Cloud-stop stays disabled until #838. |
| **Gemini** | #881 service pattern (PR #936) | (1) Make `test_no_gui_or_pyside_imports_in_services` run in a subprocess; it fails in the full CI run because earlier tests have imported Qt. (2) Add the missing frontend ESLint feature-boundary enforcement. |
| **OpenCode** | #884 (PR #933) | Nothing. Claude lands it. |

## New this round

| Agent | Issue | Why them / dependency |
|---|---|---|
| **Grok** | **#870** catalog-driven shell replacing `TabId` | Builds on Grok's #869. Coordinate shell-file edits with Cursor's #873. |
| **Grok** | **#887** S-01 gallery spike | Grok's T1 design: C++ thumbnails (middle frame) → `~/.image-toolkit/cache/render/` → `asset://`, within #930's scope. After or alongside #870. |
| **Cursor** | **#872** shortcut registry | After #873. |
| **Mistral** | **#871** design tokens → CSS variables, then **#880** settings service | After #875's PR is up. |
| **Kimi** | **#891** S-05 drag-and-drop spike | After #878's PR is up. |
| **OpenCode** | **#882** migration ledger | Start now, no prerequisites. #876 HostClient follows #875's PR. |
| **Gemini** | **#867 phase B** (one CMake build), then **#885** docs foundation | After the #881 follow-ups. |
| **Codex** | Review queue | Gate A re-review comes first. |

Codex's review queue, in priority order:

1. **Gate A re-review (#825–#833)** against
   `cloud_jobs_gate_a_review_2026-10-19.md`. Post PASS or blockers.
2. Every round-3 PR above.
3. **#812** (training memory flags; also needs the LoC split and a rebase
   onto the renamed tree), then **#819**.
4. The Dependabot PRs: #813–#816, #820, #821, #823, #923, #925, #927.

## Gates

- **Cloud Jobs Gate B** (#834–#840) is **on hold** until both:
  - Codex's Gate A PASS;
  - #879's remaining work: supervisor-enforced PID/TTL/session binding at
    mint time, and protecting the daemon key file from other processes of
    the same OS account.
- **Cloud Jobs Gate D** (#847–#852) waits for the Convert pilot #894. P-01
  #894 needs #870, #876 and #881 first, so it's **next round**, for Kimi.
- **Spikes not started yet:**
  - S-02 #888 canvas (Gemini);
  - S-03 #889 tray-per-OS (Cursor);
  - S-04 #890 ComfyUI (Kimi);
  - S-06 #892 video (Kimi);
  - S-07 #893 wallpaper (Cursor).

  They stay queued with their owners. Start them only when your
  carry-over is done.
- **Feature waves #895–#921** stay unclaimed until their wave opens.
- **Waiting on Harbinger:** archiving the four absorbed repos.
