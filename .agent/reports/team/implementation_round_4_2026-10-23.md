# Implementation round 4 — 2026-10-23

— Claude, coordinator. Roles unchanged: **Claude oversees** (GitHub upkeep,
delegation, landing), **Codex reviews and makes final edits**, **Grok
develops**; the other agents take the rows below as in round 3.

## Rules (changed or reinforced)

- **PRs target `main`, never another feature branch.** In round 3 #942, #948
  and #967 merged into their stacked bases and never reached main; they
  were re-landed as #970–#972. If your work depends on an open PR, wait for
  it to land or rebase onto main after it does.
- **Push every review fix to the PR branch before the PR is merged.** The
  #950 canvas traversal fix landed after its merge and had to be re-landed.
- **History was rewritten on 2026-10-23** (co-author trailers removed).
  Re-sync before starting: `git fetch origin`, then branch from
  `origin/main`. Do not merge or pull an old `main` into a branch.
- RESOURCE RULE, flow and CI baseline as in round 3 (only lychee fails on
  main; Dependabot/preview-deploy failures are known).
- The 500-code-line gate applies to `.rs` and `.ts`/`.tsx` too. Split before
  review, not after (`bridge_commands.rs` needed #977).

## State at the start of round 4

- **Wave 0 foundations are on main:** shell and catalog, contracts,
  supervisor, tray, bridge, HostClient and sidecar, EventHub, services,
  settings, tokens, shortcuts, ledger, docs and guardrails.
- **Convert pilot #894 landed (#976).** Wave 1 is open: Cloud Jobs Gate D,
  then Library, System, Web, Deep Learning, Wallpaper, Editors, Settings.
- **Open Wave 0 items:** #879 (binding enforcement), #883 (parity harness),
  #886 (packaging), #867 (remaining phases), spikes S-03/S-04/S-06/S-07.
- **Gate A (#825–#833):** only Grok's local note records a PASS. There is no
  Codex PASS artifact. Codex posts PASS or blockers first.

## Assignments

| Agent | Issue | Notes |
|---|---|---|
| **Grok** | **#879** supervisor-enforced PID/TTL/session binding at mint time; key-file protection | Plan merged in #969. Implement `enforce_binding` and wire the supervisor mint path. Unblocks Gate B. |
| **Cursor** | **#847** `cloud.jobs` window shell (Gate D1) | Builds on the #873 tray/window role map. First Gate D row; others build on its shell. |
| **Cursor** | **#889** S-03 tray per OS, then **#893** S-07 wallpaper | After #847. OS checklist for Harbinger. |
| **Gemini** | **#848** Jobs table and Detail (Gate D2) | After #847's shell PR is up. |
| **Gemini** | **#886** packaging during coexistence | Tauri bundle plus the PyInstaller installers; the sidecar runtime staging from #976 is the base. |
| **Kimi** | **#850** Submit surfaces (Gate D4) | After #847. Request Builder shares one form. |
| **Kimi** | **#890** S-04 ComfyUI isolated view, then **#892** S-06 video | Spikes: written go/no-go note each. |
| **Mistral** | **#851** Cloud Jobs settings (Gate D5) | On the #880 settings service. |
| **Mistral** | Tailwind v4 migration (new issue) and **#925** | The frontend was pinned back to v3 in #973. Migrate config, PostCSS plugin and token CSS, or close #925. |
| **OpenCode** | **#883** parity harness | Characterization tests, old-vs-new differential diff, on the #882 ledger. |
| **OpenCode** | **#849** Resources and Spend (Gate D3), then **#852** | After #847. |
| **Codex** | Review queue | See below. |

Gate B (#834–#840) **stays on hold** until Codex posts the Gate A PASS and
#879 lands. Gate D rows may start against the Gate A services on main.

## Codex review queue (priority order)

1. **Gate A (#825–#833):** post PASS or blockers against
   `cloud_jobs_gate_a_review_2026-10-19.md`.
2. Round-4 PRs as they arrive.
3. Spike go/no-go notes: S-01 #887, S-02 #888, S-05 #891. Harbinger
   decides on your review.
4. Held Dependabot PRs: #823 (pixi, import-linter), #923 (stale uv lock),
   #927 and #940 (ASP/HIE runtime validation), plus the new batch.

## Not started (free to claim after the rows above)

- **Library wave #895–#901** and **System wave #902–#905** (the shared
  canvas host #902 is System's first row). Wave order: Gate D, Library,
  System, Web, Deep Learning, Wallpaper, Editors, Settings.
- **Waiting on Harbinger:** spike go/no-go decisions; archiving the four
  absorbed repos; the Windows/macOS OS checklists.
