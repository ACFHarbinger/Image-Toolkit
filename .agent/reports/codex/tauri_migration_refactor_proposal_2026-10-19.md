# Tauri migration and refactor — Codex proposal

— Codex, 2026-10-19. Proposal only; preserves all recorded migration decisions.

## 1. One service boundary, extracted feature by feature

Recommend the hybrid bridge: React → narrow Rust transport → supervised Python sidecar over versioned JSON-RPC/stdio → application services → existing Python/C++ implementations. Django is a remote adapter over those services. Rust owns native capabilities, not a second implementation of image processing or database rules. This follows the devtool D51/D52 precedent in `docs/moon/roadmaps/development_tool.md`.

Evidence: `frontend/src/api.ts` hard-codes localhost:8000 and decodes responses without checking HTTP status. `frontend/src-tauri/src/core_commands.rs` separately implements conversion/merge; `video_commands.rs` launches FFmpeg and Python, while `auth_commands.rs` launches both `python` and `python3`. Consolidate these paths behind one configured runtime and typed error mapping. Do not delete them before replacement scenarios pass.

Extract one vertical feature at a time: existing Qt controller → shared use case → existing backend → Tauri view. This gives visible progress and a working comparison without a project-wide service rewrite first. Keep Qt signal/thread adapters in `gui/`; move orchestration from workers such as `gui/src/helpers/core/conversion_worker.py` only where it represents domain behavior. C++ remains the heavy processing implementation. Dependency injection belongs at the composition root; avoid one interface per trivial helper and a universal service locator.

Tradeoff: two transport adapters need conformance tests, but share behavior. Django alone is viable if measured startup, offline use and packaging are acceptable; it does not inherently require Redis/Celery for every operation. Do not choose the bridge on unmeasured startup claims.

## 2. Separate application sessions from durable jobs

The UI-owned sidecar is a command/query gateway. A separately supervised job executor owns durable work. Cloud Jobs already has its daemon/leader model: adapt to it, do not introduce a competing cloud scheduler. Preview requests can die with their UI session; accepted durable work needs an explicit owner and recovery record.

Proposed envelope: protocol version, request ID, operation ID, typed payload and structured error. Job events carry job/attempt identity and monotonic sequence numbers. Reconnect uses a cursor plus snapshot/resync when history expires; bounded buffers coalesce progress while preserving terminal state. Cancellation is a request followed by an acknowledged terminal outcome, not merely a cancelled JavaScript promise. Duplicate mutating requests need idempotency keys.

Keep stdout exclusively for framed protocol messages and stderr for redacted diagnostics. Spawn the packaged runtime explicitly, validate readiness/version before commands, bound restart attempts and avoid importing Torch at shell startup. Multi-window sessions share the host gateway. An app restart must reconnect to jobs rather than replay submissions blindly. Tradeoff: lifecycle ownership adds infrastructure, but avoids orphaning work when windows close.

## 3. Settings, vault and catalog are early foundations

`gui/src/preferences/store.py` already defines DEVICE/ACCOUNT/SESSION scopes and change subscriptions; preserve these semantics. Its `RLock` is process-local, so it cannot coordinate two GUIs. `adapters/qsettings_adapter.py` is the Qt-specific persistence boundary. Extract definitions and validation into a Qt-free service, keep the old adapter for migration, and introduce revision-checked writes plus notifications for both clients. Secrets stay in VaultManager and never become ordinary settings payloads. Retain an explicit export/rollback path; never reset preferences silently.

Reuse catalog identities from `gui/src/modules/catalog.py` and `application_catalog.py`. `descriptor.py` directly imports QWidget and carries widget factories/instances: separate serializable route metadata from Qt construction details instead of copying those types into the backend. Use the resulting metadata for discovery and parity inventory, with manually authored behavior scenarios. A generated route list alone cannot discover dialogs, keyboard behavior, tray flows or data-loss risks.

Move auth/vault/settings access and minimal packaging into the first platform slice, before Cloud Jobs UI depends on them. The full settings screen can migrate later. Tradeoff: compatibility adapters temporarily remain, but avoid two writable sources of truth.

## 4. Media access and embedded content need explicit boundaries

`frontend/src-tauri/tauri.conf.json` currently has `csp: null` and an enabled asset protocol scoped to `**`. Replace that broad starting point before adding remote embedded content. Serve media through authorized asset identities/scoped roots, with canonical path checks, symlink handling, content types and range support for video. Do not serialize entire image libraries or base64 media through the control RPC channel.

Use paginated/cursor-based queries, bounded thumbnail requests, cancellation on navigation and a byte-budgeted cache. Preserve selection by stable asset ID, not current row position. Validate output paths on the service side. These are architecture requirements; precise performance thresholds remain to be agreed. Under R5, specific intractable optimizations may be deferred; record their evidence and follow-up in the parity row (proposed tracking mechanism).

ComfyUI should have a separate origin/view with no filesystem, shell, vault or job-management privileges. Explicitly allow only necessary messages through a narrow host interface. Check embedding headers, WebSockets, focus/shortcuts, drag/drop, downloads and each target webview; a webview does not automatically establish parity. Keep the external-browser escape route.

Tauri's capabilities documentation warns that permissions merge when a view belongs to multiple capabilities. Design and test the combined permissions, not just individual files. [Official capabilities documentation](https://tauri.app/security/capabilities/). Configuration supports explicit security and asset scopes. [Official configuration reference](https://v2.tauri.app/reference/config/).

## 5. Parity means observable behavior and recoverable upgrades

Agree with Claude's capability-based parity matrix and Convert pilot. Add per-feature scenarios for inputs/outputs, settings migration, cancellation, errors, keyboard accessibility, window reopening and applicable OS behavior. Compare golden artifacts for deterministic operations; use tolerances and metadata checks where exact binary output is inappropriate. Reuse acceptance intent from Qt tests without forcing identical click sequences on different UIs.

Move cheap feasibility checks for galleries, native integration and embedded ComfyUI early, even if full ports come later. Otherwise the easy Convert pilot leaves the largest risks unresolved. No benchmark or desktop experiment is launched by this proposal.

Current Tauri documentation distinguishes direct `tauri-driver` support from WebdriverIO's embedded-server route, which also supports macOS. Select and verify the actual toolchain per platform; do not assume one driver covers every OS. Browser-only React tests cannot prove native tray/file-dialog/IPC parity. [Official WebDriver guide](https://v2.tauri.app/develop/tests/webdriver/).

Package the UI/sidecar as a tested pair with a startup compatibility handshake. Remote clients negotiate supported schema/features. Plan rollback around data migrations: additive changes while both GUIs ship, destructive migrations only after old readers retire. Updates must not terminate durable cloud jobs. The canonical app version remains root `pyproject.toml`; use the existing version bump workflow rather than introducing a second manual version source.

## 6. Modular integration and developer documentation

Following R7, prefer folding HIE/ASP/CSG frontend code into the main app. Use reusable views and a small host interface selectively where they help navigation, asset selection, commands, task events, settings and theme tokens; retain standalone shells only where useful. Keep React and native host dependencies out of shared domain contracts. Avoid runtime plugin loading until a real requirement needs it. Tradeoff: consolidation couples releases and requires clear ownership of moved code; selective shared interfaces preserve useful reuse.

Enforce dependency direction incrementally: views → public feature API; transport adapters → services; services → domain/repository protocols; implementation adapters → existing backend/C++. Start boundary checks on migrated modules and grow coverage without a blanket waiver. Every extracted slice removes or delegates its previous implementation.

Documentation deliverables per slice: concise module README, public contract/errors, process owner and cancellation semantics, one runnable development example, and targeted test commands. Add an architecture map with local/remote process diagrams, a debugging guide for sidecar readiness/events, and ADRs for decisions that are actually locked. Use Convert as the “add a feature” walkthrough. Link generated references rather than manually duplicating schemas. Keep operational agent history separate from human onboarding docs.

## Suggested sequence

1. Agree bridge, lifetime, settings ownership and parity criteria; create catalog/behavior inventory.
2. Build minimal platform contracts, settings/vault access, supervision and packaged startup; Convert vertical slice.
3. Resolve high-risk media/embedding/native feasibility; build Cloud Jobs Gate D on the shared bridge while its backend gates continue.
4. Migrate area slices, removing each Qt feature only at its agreed parity gate; extend docs and boundary checks with each slice.
5. Retire remaining Qt adapters/dependencies once callers and rollback obligations are gone.

Validation should start with targeted contract, restart, cancellation, settings-conflict and media-authorization checks. Full suites and performance runs need the existing Harbinger authorization chain. No implementation or tests were run for this proposal.

## Questions and recorded answers

Harbinger's answers supersede the original recommendations where they differ. Recorded by Codex, 2026-10-19; overall scope awaits the team final round.

- **[Codex R1] Which desktop bridge should we standardize on?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Supervised Python sidecar over versioned JSON-RPC/stdio; Django exposes the same services remotely; Rust handles native integration.
  - **A (recommended):** supervised Python sidecar with versioned JSON-RPC over stdio; Django exposes the same services remotely; Rust handles native integration.
  - **B:** supervised local Django API for desktop and remote clients; fewer transports, larger desktop server footprint.
  - **C:** sidecar with authenticated loopback HTTP and streamed events; easier browser tooling, but requires port discovery and local endpoint security.
- **[Codex R2] Should local work survive closing every app window?** Cloud jobs already must survive.
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Durable long-running local jobs survive closing all windows under an independent supervisor; previews and interactive requests remain session-owned. Cloud jobs retain their independent lifecycle.
  - **A (recommended):** mark long jobs as durable and run them under a supervisor independent of the UI; previews and interactive requests remain session-owned.
  - **B:** keep all submitted local jobs running until completion, even short jobs; more background resource use.
  - **C:** cancel local jobs on exit after warning; cloud jobs retain their existing independent lifecycle.
- **[Codex R3] How should settings behave while both GUIs ship?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Both GUIs use one settings service with preserved keys/scopes, conflict detection and a backed-up migration of legacy settings.
  - **A (recommended):** both use one settings service with preserved keys/scopes and conflict detection; migrate legacy data with a backup.
  - **B:** import once into Tauri, then keep separate settings; simpler, but changes stop following the user between apps.
  - **C:** keep independent stores with bidirectional synchronization; more conflict and recovery complexity.
- **[Codex R4] How should ComfyUI be hosted?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Isolated embedded ComfyUI view without native privileges, enabled after compatibility/security checks, with an external-browser fallback.
  - **A (recommended):** isolated embedded view without native privileges, enabled after a compatibility/security check, plus an external-browser fallback.
  - **B:** external browser only throughout the migration; lower integration cost.
  - **C:** a dedicated isolated Tauri window, keeping the main workspace separate; still requires the same checks.
- **[Codex R5] What performance evidence should block retiring a PySide6 feature?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A as the target, with C permitted for specific areas where optimization proves intractable. Aim for agreed responsiveness and memory budgets; defer difficult optimizations rather than blocking the entire migration. This is a case-specific exception, not a blanket removal of performance gates.
  - **A (recommended):** agreed responsiveness and memory budgets on representative datasets, alongside functional parity.
  - **B:** no material regression against measured PySide6 baselines; faster to define, but can preserve existing slow behavior.
  - **C:** functional parity first; performance tuning afterward, accepting temporary regressions.
  Measurements requiring benchmarks or full suites still follow the Codex/Harbinger authorization chain.
- **[Codex R6] How should desktop/backend updates stay compatible?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** A. Ship desktop UI and sidecar as a tested version pair; remote servers negotiate a documented compatibility range.
  - **A (recommended):** ship desktop UI and its sidecar as one tested version pair; remote servers negotiate a documented compatibility range.
  - **B:** allow independent UI/sidecar updates within a supported protocol range; more flexible, larger compatibility matrix.
  - **C:** require exact versions for desktop and remote clients alike; simplest rules, disruptive coordinated upgrades.
- **[Codex R7] How should HIE, ASP and CSG join the main app?**
  - **Harbinger answer (2026-10-19; recorded by Codex):** Mostly C, with A where it makes sense. Prefer folding HIE/ASP/CSG frontend code into the main app; retain reusable views/shared host interfaces selectively where useful. Standalone shells are not a universal requirement.
  - **A (recommended):** package their views behind a small shared host interface; retain their standalone shells as adapters.
  - **B:** launch their standalone apps from the main app; simpler integration, fragmented navigation and state.
  - **C:** fold their frontend code into the main app; fewer shells, tighter release coupling and more disruptive repository changes.
