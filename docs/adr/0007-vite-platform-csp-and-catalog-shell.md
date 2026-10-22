# ADR-0007: Vite Build, Default-Deny Tauri Capabilities, Catalog Shell, and Design Tokens

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#868](https://github.com/ACFHarbinger/Image-Toolkit/issues/868), [#869](https://github.com/ACFHarbinger/Image-Toolkit/issues/869), [#870](https://github.com/ACFHarbinger/Image-Toolkit/issues/870), [#871](https://github.com/ACFHarbinger/Image-Toolkit/issues/871), [#872](https://github.com/ACFHarbinger/Image-Toolkit/issues/872), [#873](https://github.com/ACFHarbinger/Image-Toolkit/issues/873)

## Context

`frontend/` originally used Create React App (CRA) with leftover Electron shims, a hardcoded `TabId` union in `App.tsx`, manual CSS styling disconnected from Qt's theme tokens, and permissive window permissions.

## Decision

1. **Vite + React 19 and Electron removal (#868):** Replace CRA with Vite and delete all Electron remnants before feature waves begin.
2. **Security lockdown (#868):** Enforce a real Content Security Policy (never `csp: null`), one Tauri 2 capability file per labeled window (`frontend/src-tauri/capabilities/*.json`), and a default-deny `asset://` scope that never includes original user library directories. Enforced in CI by `middleware/validation/check_tauri_security.py`.
3. **Serializable module catalog and catalog-driven shell (#869, #870):** Extract a Qt-free serializable module catalog from `descriptor.py` whose IDs match `migration/features.toml`. Rail, ribbon, inspector, and status bar render directly from the catalog, replacing `App.tsx`'s `TabId` union.
4. **WindowManager role map and native tray (#873):** Use one main webview with a `WindowManager` role map for labeled pop-outs (such as `cloud.jobs`), native tray integration, and hide-all-on-close semantics.
5. **Generated design tokens and shared shortcut registry (#871, #872):** Generate CSS custom properties from `gui/src/theming/tokens/{light,dark}.json` (never port QSS by hand) and share one serializable shortcut registry (`keybindings.json`) across both shells, reserving OS global shortcuts strictly for tray show/hide.
6. **Embedded ComfyUI isolation (#890):** Embed ComfyUI only inside an isolated view with zero native Tauri privileges after compatibility/security checks, retaining external browser launch as a fallback.

## Consequences

- Adding or restructuring a capability requires updating the catalog and ledger rather than editing hardcoded union types.
- CI automatically blocks wildcard Tauri permissions, missing CSPs, or unmapped window capabilities.
