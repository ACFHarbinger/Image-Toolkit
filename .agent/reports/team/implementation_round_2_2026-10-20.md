# Implementation round 2 — 2026-10-20

Delegated by Codex at Harbinger’s request, after Grok’s Wave 0 review. This round supersedes the first-prompt queue in the 2026-10-19 handover. Later backlog ownership stays as recorded unless explicitly changed here.

## Roles

- **Grok returns to implementation**, starting with #869. The temporary assignment to review every PR ends for this round.
- **Codex resumes review, final edits and landing**, and delegates this round. Codex also owns the outstanding Gate A re-review and #846’s resource/run authorization queue.
- **Claude resumes GitHub issue/project maintenance now and delegates the following round.** Claude’s operational handoff is in `claude_coordination_handoff_2026-10-20.md` beside this report.
- Harbinger retains spike go/no-go decisions and authorization for each full suite/benchmark or paid run. The resource rule is unchanged.

## Deliveries to reconcile first

Grok’s bus review is the review record; completed implementation is not the same as a merged PR.

| Deliverable | Verified state at this handoff | Delivery action |
|---|---|---|
| #877 supervisor / PR #929 | Open; reviewed head `a157e3134`; unit/slow CI still running | Claude tracks CI and queues landing with Codex. Preserve the outstanding shell focus hookup for #873. |
| #868 Vite/security / PR #930 | Open; reviewed head `76cf4a82d`; C++/unit/slow CI still running | Claude tracks CI; Codex lands once ready. Frontend work integrates on this baseline. Originals no longer display directly; the render-cache path is an explicit later integration. |
| #874 contracts / PR #931 | Open; head `ea6fe461a`; Grok reviewed without changes; all reported checks successful | Claude queues Codex landing. #875 must enforce runtime enum/const validation beyond generated scalar types. |
| #879 sealed leases | On main: `058a064be` plus Grok’s `711cc2353` fix | Gemini addresses the explicit security-boundary follow-up below; Claude records implemented versus follow-up readiness accurately. |
| #884 guardrails | Reviewed changes remain uncommitted on the shared checkout, including Grok’s AGENTS.md correction | OpenCode commits only its own changes and supplies the PR/commit plus targeted validator evidence before advancing its new work. |
| Cloud Gate A #825–#833 | Implemented; no explicit final PASS located in the bus for `2d44f57c4` | Codex owns the remaining re-review; Claude does not close these on a general Wave 0 review alone. |

The shared checkout contains OpenCode’s #884 edits. Do not stash, reset, rebase, or switch branches over them. Use isolated worktrees for the new implementation round.

## Assignments

| Agent | Issue/task this round | Deliverable and dependencies |
|---|---|---|
| **Grok** | **#869 — W0-05 serializable catalog** (reassigned from Gemini) | Extract data-only IDs, categories, routes, window roles and capability metadata from widget construction. Preserve route IDs and use the same serializable metadata in both shells. Coordinate the public shape with #870 and the future #882 ledger; do not create a second route registry. #887 stays a later spike; do not expand this PR into thumbnail implementation. |
| **Gemini** | **#879 security-boundary follow-up, then #881 service pattern** | First address Grok’s concrete findings: production Python bindings still accept raw key bytes through `create_raw_store_lease`/`set_transit_key`, and the shared per-user transit-key file does not establish a per-daemon secret. Keep production key material and lease handoff in native code, validate process/supervisor binding, and test a genuine separate daemon process using isolated test roots. Do not claim the sealed-lease readiness gate while these remain unresolved. Once this fix is reviewed, implement #881’s small Command/Handler + Protocol service pattern and boundary checks, coordinated with #867’s later consolidation. Use separate PRs. |
| **Cursor** | **#873 — W0-09 native tray and window roles** | After #930 lands, implement Tauri tray, hide-all on close, explicit window labels/pop-outs and routing/focus requests. Consume #877’s supervisor instead of adding another process manager. Wire the `request_focus` caller noted in Grok’s review. The independent OS spike #889 remains queued; prepare focused local evidence and note checks Harbinger must run. |
| **Mistral** | **#875 — W0-11 shared bridge package** | After #931 lands, own framing, request IDs, handshake/version negotiation, typed errors and cancellation. Validate JSON-RPC const fields, enum values and request/response structure at runtime, including Rust’s weaker generated scalar types. Publish the transport API early for OpenCode/Kimi. No business logic or second schema source. Coordinate frontend dependencies with landed #930. |
| **Kimi** | **#878 — W0-14 generated EventHub** (reassigned from Mistral) | Use #874’s channel schemas for intents/facts, sequence numbers, snapshot plus bounded tail, gap detection and resnapshot. Keep `appStore.ts` ephemeral. Begin pure reducer/buffer tests against schema fixtures; integrate #875’s transport as it becomes available. No parallel RPC envelope. #894 remains blocked on the complete platform/parity foundations. |
| **OpenCode** | **Deliver #884, then #876 — W0-12 sidecar/HostClient** | Commit the reviewed guardrail edits with targeted validator evidence first. After the #874/#875 contracts land, implement the JSON-RPC/stdio sidecar and HostClient transport adapters with a conformance slice: explicit readiness/version handling, bounded reconnect, cancellation/errors and clean stdout framing. Connect to #877’s supervisor, use an explicit installed runtime and keep heavy ML imports off startup. Leave #882/#883 for a subsequent bounded round. |
| **Codex** | **Review/final edits, Gate A re-review, landing** | Take the incoming PR queue back from Grok. Review `2d44f57c4` against the three previously reported Gate A blockers, then review the #879 follow-up against the native-key/daemon boundary. Carry #812/#819 and dependency PR reviews forward; no implementation agent is assigned the same work twice. |
| **Claude** | **GitHub maintenance and preparation for the following round** | Apply the ownership/status changes in the handoff note, reconcile delivered PRs/issues, track dependencies and acceptance evidence. Delegate the next round after this one reports its results. |

## Gates and completion

- This opens the listed platform work. Cloud Gate B stays conditional on a recorded Gate A PASS, landed #877 and accepted #879 sealed-lease readiness. #834–#840 may be planned, but are not marked unconditionally Ready by this delegation.
- Shared dependencies: #874 → #875 → #876, with #878 consuming the same transport. #869 supplies the catalog consumed by the later #870 shell. Frontend integration uses landed #868; no competing package/lockfile rewrite.
- No feature-wave or Cloud Gate D opening yet: Convert #894 still needs settings, ledger/parity, service and bridge foundations.
- Each owner posts a claim and submits a bounded PR with targeted checks. Report the base commit, issue, public interfaces changed, test evidence and remaining integration work on the bus. Codex reviews/final-edits; Claude maintains the issue/project record. Codex lands reviewed changes.
- A reported PASS must identify the actual commit. Re-read current CI before landing; an old green run does not cover a later review edit. Do not assume every lychee failure is baseline without comparing its failing links.
