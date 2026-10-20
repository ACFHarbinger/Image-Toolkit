# Coordination and assignments — 2026-10-19

**Superseded role/round allocation (2026-10-20):** see [round 2](implementation_round_2_2026-10-20.md) and [Claude’s handoff](claude_coordination_handoff_2026-10-20.md). Grok implements; Codex reviews/lands; Claude maintains GitHub now and delegates the following round. The allocation below is the prior-round record.

Codex takes over Claude’s coordination/delegation role at Harbinger’s request. Grok takes over Codex’s review and final-edit role. This allocation supersedes the earlier proposed owner tables; ownership uses the existing `agent:<name>` labels.

## Roles and gates

- Codex maintains issues, board, roadmaps and landing; retains #846 (live-test marker/runbook and authorization queue).
- Grok reviews every PR, commits necessary final corrections, and supplies the second review for deletion rows. No implementation queue remains assigned to Grok.
- Landing order: implementation owner → Grok review/final edits → Codex landing. Harbinger retains spike go/no-go and resource authorization decisions.
- RESOURCE RULE is unchanged: only Codex runs full suites/benchmarks, after explicit Harbinger approval per run; one at a time, monitored. Single-file/selected tests remain available to implementation owners and Grok.
- Gate A #825–#833 is **In review**, not closed. Gate B stays **On hold** until Grok passes Gate A and #877/#879 land. Cloud gates then open in order. Gate D also requires the Convert pilot #894 and Tauri platform readiness.
- Tauri #865/#866 and #867 phase A landed. #867 phases B–D remain. Feature waves #895–#921 stay free to claim only when their wave opens.
- Both package renames are complete: Python `middleware.…`, C++ `import backend`; no old aliases. Cloud store is encrypted `cloud_jobs.db`; no PostgreSQL or cross-machine leader/observer. Store access moves to C++ sealed leases via #879, consumed by #835.
- Work on isolated branches/worktrees; claim on the issue/bus, one capability per PR, stage only own paths, never stash another agent’s work. Assignment alone does not open a blocked gate or authorize paid work.

## Prompt these agents first

| Agent | Start with | Next queue |
|---|---|---|
| Grok | Re-review #825–#833, especially `2d44f57c4` against the three paid-execution blockers | #812 (review + LoC split), #819 (review), then dependency PR queue |
| Gemini | #879 sealed per-store leases | #869 catalog; #867 phases B–D and remaining foundations |
| Cursor | #877 supervisor, using fake sibling processes first | #873 tray/window roles after #868; integrate #875/#876; then other assigned work |
| Mistral | #868 Vite/security/Electron-removal foundation | #875 after #874; #871/#878, then #880 |
| Kimi | #874 contracts and method-routing table | #890/#891/#892 after platform prerequisites; #894 pilot once foundations pass |
| OpenCode | #884 freeze/migration guardrails | #882 ledger, then #876 after #874/#875; #883 parity harness |

These are initial queues, not instructions to open later gates. Coordinate common files before parallel edits.

## Complete assigned implementation queue

- **Gemini:** Tauri #867, #869, #879, #881, #885, #887, #888; Cloud Jobs #840, #848, #853, #858.
- **Cursor:** Tauri #870, #872, #873, #877, #886, #889, #893; Cloud Jobs #835, #836, #841, #847, #857.
- **Mistral:** Tauri #868, #871, #875, #878, #880; Cloud Jobs #839, #845, #851, #854, #856, #859.
- **Kimi:** Tauri #874, #890, #891, #892, #894; Cloud Jobs #837, #838, #844, #850, #860, #863.
- **OpenCode:** Tauri #876, #882, #883, #884; Cloud Jobs #834, #842, #843, #849, #852, #855, #861, #862.
- **Codex:** coordination/tracking #824/#864; live-test marker/runbook and authorization queue #846.

Codex also owns tracking issues #824/#864. Grok owns the review queue #825–#833 and PR reviews, not the implementation tasks listed above. Claude has no remaining open implementation assignment in these two initiatives.

## Grok’s review handoff

1. Read `.agent/reports/codex/cloud_jobs_gate_a_review_2026-10-19.md`, the bus entry “Codex’s three Gate A blockers fixed”, and `2d44f57c4`; confirm authoritative preflight/revalidation, serialized monthly reservations, and graceful cleanup/output collection after failures. Confirm rename compatibility with the current `middleware/` and C++ `backend` module. Check that `backend.__file__` points to the compiled extension: the C++ source directory also imports as a namespace package, so `importorskip` alone is insufficient.
2. Review against actual main/PR diffs, not claimed completion. Apply final edits on the author’s branch; report the commit, targeted checks and residual blockers on the issue and bus. Ask Codex for any full run; do not launch it.
3. Then handle #812 (including required LoC split), #819, and dependency PRs #813–#816, #820/#821/#823/#923/#925/#927. Avoid changing unrelated training behavior while resolving rename/merge conflicts.
4. Review every incoming implementation PR and deletion parity row.
5. Codex closes Gate A after your PASS and any required checks; do not mark review-pending issues Done. Harbinger decides each S-01…S-07 go/no-go after your review.

## Former Grok implementation tasks

- #869 catalog → Gemini.
- #873 tray/window roles and #877 supervisor → Cursor.
- #887 gallery/thumbnail spike and #840 worker images → Gemini.
- #851 cloud settings and #859 Hyperstack → Mistral.
- #860 Thunder Compute → Kimi.

Claude’s open tasks and Codex’s prior implementation queue are also redistributed in the complete table. Codex retains only coordination and #846. Remote repository archival remains Harbinger’s decision.

## Verification — Codex, 2026-10-20

Verified all 69 scoped open issues against GitHub agent labels and project statuses. Gate A’s nine issues remain In review with Grok; #812/#819 are also In review on the board. No implementation issue remains assigned to Grok. #824/#864 are In progress for coordination; dependent work is On hold. Ready: #846, #867, #868, #869, #874, #877, #879, #881, #882, #884, #885. Ownership uses the complete table above; the first-prompt table gives each agent’s initial queue.
