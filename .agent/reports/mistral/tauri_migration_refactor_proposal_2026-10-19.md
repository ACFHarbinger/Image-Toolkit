# Tauri Migration and Architecture Refactor — Mistral proposal

— Mistral, 2026-10-19. Proposal only. Builds on the recorded answers:
Claude Q0a–d, Codex R1–R7, OpenCode Q1–Q8, Grok T1–T8, Cursor W1–W8,
and the no-PostgreSQL correction (encrypted unified store /
`cloud_jobs.db`). Pending questions I do not re-ask: Kimi Q1–Q8 (IDL,
single-instance gate, event catch-up, spikes, e2e, branching, schema
discipline, go/no-go) and Gemini G1–G6 (C++ binding, asset streaming,
canvas engine, extraction pattern, submodule unification, docs).

My additions: the Tauri 2 capability ACL as the concrete Wave 0
lockdown mechanism, a minimal ordered Wave 0 cut, the bridge restart
contract, a route-map field for the migration ledger, and five scoping
questions nobody has asked (navigation restructuring, wave order,
accessibility, i18n, sidecar embedding during coexistence).

## 1. Tauri 2 capability ACL as the Wave 0 lockdown mechanism

Grok T2 decided default-deny asset scope and a real CSP before any new
UI. The concrete mechanism already exists in the repo:
`frontend/src-tauri/capabilities/default.json` grants `core:default`
and `dialog:default` to the `main` window only, while
`tauri.conf.json` still has `csp: null` and asset scope `**`.

Proposal:

- one capability file per labeled window (Cursor W1's `cloud.jobs`
  pop-out gets its own file, with no `**` asset scope, as already
  decided);
- asset-protocol scope declared per capability file, so each feature
  declares its roots (T2) against the window that renders it, not in
  one global config;
- a small CI check that fails on wildcard scopes, `csp: null`, or a
  capability whose permission list isn't covered by a ledger row —
  the same "tooling, not convention" spirit as OpenCode's boundaries.

Risk: Tauri's capability syntax evolves between minor versions; the
check should pin against the shipped schema
(`gen/schemas/desktop-schema.json`) rather than parsing ad hoc.

## 2. Wave 0 as one ordered cut, not a pile

The recorded Wave 0 decisions already number nine: Vite + Electron
removal (OpenCode Q6), CSP/scope lockdown (T2), token CSS (W5), tray +
hide-all (W3), catalog shell replacing `TabId` (W8), EventHub codegen
(W2), shortcut registry (W6), the supervisor (T5), and Kimi's
single-instance gate. That is a milestone, not a wave; unsequenced, it
invites exactly the concurrent-agent collision the bus rules exist to
prevent.

Proposal — Wave 0 lands as three PRs, in order, no feature work merging
until all three are green:

1. **Build + security.** CRA → Vite, Electron deletion, CSP,
   per-window capabilities, asset scope. Purely mechanical, nothing
   user-visible.
2. **Shell.** Catalog-driven rail/ribbon/inspector, token CSS, tray,
   shortcut registry, hide-all (port of
   `gui/src/windows/main/_lifecycle.py:collect_background_windows`).
3. **Bridge spine.** Sidecar skeleton, envelope, version handshake
   (Codex R1/R6), supervisor, single-instance gate, `bridge.down` /
   `bridge.ready` events (§3 below).

Definition of done: a cold start of the Tauri shell with the supervisor
running, one route mounted from the catalog, and CI enforcing every
Wave 0 rule. Cloud Jobs Gate D then has a platform to land on.

## 3. Bridge restart contract

Kimi Q3 covers late-joining views catching up; this is the other
failure mode — the supervisor restarts a crashed sidecar while the
webview lives on (T5 guarantees the processes are siblings, not that
the UI survives reconnect).

Proposal, one path, tested:

- the supervisor emits `bridge.down` when the sidecar dies and
  `bridge.ready` (with the negotiated protocol version, R6) when it is
  back;
- views keep their route and their ephemeral state; in-flight
  session-owned requests fail with the shared error envelope (Kimi's
  `{code, retryable, message_key, details}`); durable jobs reattach on
  `bridge.ready` and re-emit progress from their persisted events;
- a CI smoke test kills the sidecar (`SIGKILL`) mid-scenario and
  asserts the recovery path end to end — the same crash-point thinking
  as the Cloud Jobs certification kit (#830), applied to the bridge.

## 4. A route-map field in the migration ledger

OpenCode's ledger already collapses 33 routes into 26 capability
records. What it doesn't capture is navigation intent: which old routes
a user could reach, and where each lands in Tauri. Proposal: each row
carries `routes: {old → catalog_id, alias?}`; any old route referenced
by a shortcut, docs page, or DB-stored preference gets a compat alias
so muscle memory and stored settings survive. This is also what makes
my M1 answerable per row instead of per initiative.

## 5. Small notes

- The supervisor's own autostart on Linux (`.desktop` autostart vs
  systemd user unit) is unaddressed by T5; systemd user units give
  socket/FD supervision and survive session quirks, but autostart is
  simpler and matches how the slideshow daemon works today. Worth one
  issue, not a question.
- `docs/moon/ROADMAP.md`'s superseded Tri-Interface section should be
  rewritten in the same PR that creates the new roadmap, so the docs
  tree never has two contradicting strategies at once.

## 6. Questions for Harbinger

All seven answered by Harbinger on 2026-10-19, matching the
recommendations; recorded inline in the shared report §5.

**Answers:** M1 — restructure within a ledger row where behavior is
preserved, route map plus compat aliases recorded, cross-row merges
need sign-off. M2 — the library/database wave follows the pilot and
Gate D. M3 — keyboard parity is a row-pass criterion, screen-reader
best-effort with known-gaps lists. M4 — i18n stays out of scope
(English-only), views avoid hard-coded concatenation. M5 — one shared
installed backend environment per machine during coexistence; the
sidecar freezes only at Qt deletion. M6 — the `bridge.down` /
`bridge.ready` contract with the SIGKILL smoke test. M7 — one shared
bridge package consumed by the main app and the devtool.

Each with options and a recommendation; none re-ask a recorded answer
or a pending Kimi/Gemini question.

- **[Mistral M1] May the Tauri app consolidate user-visible
  navigation?** OpenCode Q1 fixed the ledger unit, not whether the
  user's navigation may change.
  - **A (recommended):** restructuring allowed within a row where
    behavior is preserved; the row's route map (§4) records old →
    new; routes referenced by shortcuts, docs or stored settings get
    compat aliases. Cross-row merges need Harbinger sign-off.
  - **B:** strict 1:1 route parity until every row passes;
    consolidation is a post-migration release.
  - **C:** free restructure; the catalog is the only map. Fastest,
    breaks muscle memory and makes parity diffing harder.
- **[Mistral M2] Which area wave follows the Convert pilot and Cloud
  Jobs Gate D?**
  - **A (recommended):** library/database (gallery, search, tags,
    groups). Largest user value, first full exercise of the C++
    thumbnail pipeline (T1) and asset-protocol streaming.
  - **B:** editors (stitch, merge, frame-slice). Retires the hardest
    canvases while the Wave 0 canvas spike is fresh; front-loads the
    risk.
  - **C:** web/system (crawlers, utilities, preferences). Thinnest
    UIs, cheapest porting muscle, least user-visible progress.
  - **D:** Harbinger assigns per agent availability; no fixed order.
- **[Mistral M3] What does accessibility parity mean per row?**
  - **A (recommended):** keyboard parity is a row-pass criterion
    (one shortcut registry, W6, makes this checkable); screen-reader
    support is best-effort with a known-gaps list in each module
    README, revisited after PySide6 is gone.
  - **B:** full screen-reader parity is a row-pass criterion; deletion
    blocked until each row passes an a11y audit.
  - **C:** keyboard parity only; screen-reader work explicitly out of
    scope for this initiative.
- **[Mistral M4] Is i18n in scope?** The Qt GUI has no QTranslator or
  message-catalog infrastructure today (English-only).
  - **A (recommended):** status quo — English-only, out of scope for
    this initiative; ported views still avoid hard-coded sentence
    concatenation so extraction stays cheap later.
  - **B:** wire i18n in Wave 0 (message catalog + key extraction,
    react-i18next or equivalent); every ported view uses keys from day
    one; translations arrive later.
  - **C:** full localization before the PySide6 deletion gate.
- **[Mistral M5] How does the Tauri bundle embed the Python sidecar
  during coexistence?** W4 decided dual installers and the eventual
  frozen sidecar; it didn't decide what the Tauri installer launches
  for Python while both apps ship.
  - **A (recommended):** both installers use the one installed backend
    environment per machine; the Tauri supervisor spawns the sidecar
    from it. One Python to update during coexistence; the freeze
    happens only at Qt deletion, as W4 already decided.
  - **B:** the Tauri installer embeds its own sidecar now
    (PyInstaller-collected or python-build-standalone). Heavier
    installer; two Python environments to keep in sync mid-migration.
  - **C:** the sidecar runs from a uv-managed, first-launch-resolved
    environment (lock file shipped, interpreter fetched on demand).
    Reproducible, adds a first-run network dependency.
- **[Mistral M6] What is the recovery contract when the supervisor
  restarts the sidecar?**
  - **A (recommended):** §3 as written — `bridge.down` / `bridge.ready`
    events, error envelope for in-flight requests, durable jobs
    reattach, route preserved, and a SIGKILL smoke test in CI.
  - **B:** the webview fully reloads on sidecar restart. Simplest
    mental model; loses all UI state on every crash.
  - **C:** each view implements its own recovery. Flexible, unbounded
    divergence across 26 rows.
- **[Mistral M7] Does the main app share bridge code with the devtool
  sidecar?** The devtool precedent (D51, `dev/tool/devtool.py`) chose
  the same model Codex R1 chose for the main app.
  - **A (recommended):** extract one small bridge package (framing,
    envelope, version handshake, generated clients) consumed by both;
    the devtool migrates opportunistically, not blocking any wave.
  - **B:** the main app builds its own bridge; the devtool keeps its
    private one. Accept the duplicate until the devtool's next major
    revision.
  - **C:** make the devtool's sidecar the canonical package and consume
    it from the main app. Couples the app's release cadence to a dev
    utility.

— Mistral
