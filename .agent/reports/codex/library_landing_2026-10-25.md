# Library and canvas landing — 2026-10-25

Merged all completed pending deliveries and deleted their remote branches. No open PRs remain at verification.

| PR | Delivery | Merge commit |
| --- | --- | --- |
| #998 | Preview/compare, including bounded RGBA previews and alpha-aware differences | `cfd0d537f` |
| #1001 | Canvas texture residency and alpha blending fixes | `7297b72cf` |
| #999 | Listings capability and view | `e59524eac` |
| #1002 | Image search capability view, prepared branch opened after #999 | `8e3990d9d` |
| #1000 | Management and data browser | `73b18b657` |
| #995 | brotlicffi lock update | `9d470f588` |
| #996 | brotli lock update | `6aa455759` |
| #997 | ASP/HIE grouped lock updates | `d19471580` |
| #1003 | Scan/tag with actual metadata persistence, prepared branch opened and integrated | `8340d6759` |

Integration preserved every capability's methods, injected stores, dispatch handlers, HostClient methods and catalog views. Regenerated bindings from source schemas rather than editing generated files. Renamed colliding library-admin EmptyParams/GroupRecord schema types to AdminEmptyParams/AdminGroupRecord. Updated handshake expectations, schema-specific module hashes and parity output. Changelog entries accompany the code corrections.

Final main checks: contracts freshness, docs freshness, migration ledger, Tauri security baseline, offline uv lock check, TypeScript, and the selected sidecar server file (16 passed). Earlier targeted checks passed for preview (14), canvas (4 production + 6 rendering), listings (5 service + 4 dispatch + 4 view), management (8 service + 2 view), image search (4 view), and scan (7 service + 4 view). Handshake selections passed after catalog integration. Small isolated dependency probes verified both Brotli implementations and file-lock exclusion; all affected dependency lock checks passed.

No full suites, benchmarks, corpus runs, model runs or live cloud operations launched locally. Automatic GitHub CI runs were not treated as fresh local evidence; some optional runs were pending at merge. No required branch checks were configured. The known external-link check still encounters existing 403/429 URLs; it is not a product regression from these changes.

Interactive desktop/OS parity and live provider signoffs remain separate. Gate B stays closed; merging page projections does not attach a vault session or open a store. Local worktrees and local branch refs were retained; remote source branches were deleted only after confirmed merges.
