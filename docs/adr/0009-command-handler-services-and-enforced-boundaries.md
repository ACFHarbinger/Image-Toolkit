# ADR-0009: Command/Handler Service Layer and Tool-Enforced Module Boundaries

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#881](https://github.com/ACFHarbinger/Image-Toolkit/issues/881)

## Context

Previously, domain orchestration was scattered across `gui/src/helpers/` (`QThread` workers), `middleware/src/core/`, and `frontend/src-tauri/` Rust commands, with global singletons and implicit cross-feature imports making unit testing and UI migration difficult.

## Decision

1. **Service-layer layout (`middleware/src/services/<feature>/`):**
   - Each capability lives in `middleware/src/services/<feature>/` and exposes its public surface through `services/<feature>/api.py`.
   - `gui/` (thin `QThread` shims until row deletion), `frontend/` (via the sidecar), and `api/` (Django) are all clients of this layer.
2. **Command/Handler + Protocol pattern:**
   - Commands and Results are immutable (`@dataclass(frozen=True)`) value objects.
   - Handlers and Services implement `@runtime_checkable` `Protocol` interfaces (`Handler[C, R]`, `ServiceProtocol`).
   - Dependencies (repositories, settings, native wrappers) are constructor-injected; global singletons are prohibited.
   - Sibling features communicate only through contracts or EventHub.
3. **Automated boundary and size gates:**
   - **Python (`import-linter`):** `middleware.src.services` must never import `gui` or `PySide6`, and sibling service packages under `middleware.src.services.*` are independent.
   - **TypeScript (`eslint-plugin-boundaries`):** `frontend/eslint.config.mjs` forbids cross-feature (`src/features/<x>/`) and cross-tab-domain (`src/tabs/<domain>/`) imports, and prevents shared hooks/components/math from importing shell or feature views.
   - **LoC gate (`count_loc.py`):** Enforces a 500-code-line ceiling across `middleware/src`, `gui/src`, and `frontend/src`.

## Consequences

- Every capability can be tested headlessly in Python without Qt (`PySide6`) loaded in `sys.modules`.
- Architectural boundary violations fail CI immediately in both Python and TypeScript.
