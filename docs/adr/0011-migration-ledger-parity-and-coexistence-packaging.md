# ADR-0011: Capability Migration Ledger, Differential Parity Oracle, and Coexistence Packaging

- **Status:** Accepted (Locked 2026-10-19)
- **Tracking:** [#882](https://github.com/ACFHarbinger/Image-Toolkit/issues/882), [#883](https://github.com/ACFHarbinger/Image-Toolkit/issues/883), [#884](https://github.com/ACFHarbinger/Image-Toolkit/issues/884), [#886](https://github.com/ACFHarbinger/Image-Toolkit/issues/886)

## Context

Migrating a large desktop application across 9 feature waves risks orphaned routes, silent behavioral regressions, or premature deletion of working PySide6 code before Tauri parity is proven on target operating systems.

## Decision

1. **One ledger record per capability (`migration/features.toml`, #882):**
   - `migration/features.toml` tracks one record per capability (e.g., Stitch covers 8 routes; Deep Learning covers 5 routes).
   - Each record declares catalog route IDs and legacy route aliases, PySide6 paths, Tauri paths, service/contract paths, parity scenarios, documentation path, owner, wave, status (`pyside-only` | `both` | `parity-passed` | `pyside-deleted`), and an OS verification checklist.
   - CI validates bidirectional route coverage and path existence, and generates `docs/migration/parity.md`.
2. **Characterize-then-diff parity oracle (#883):**
   - Existing PySide6 tests (~224 files) serve as the behavioral parity oracle and are deleted only in the PR that deletes the PySide6 code they cover.
   - Each migrating capability runs differential parity tests comparing the legacy path against the new service on identical fixtures in CI, supplemented by Playwright tests (against Vite + contract mocks on every PR) and `tauri-driver` WebDriver smoke checks per release.
3. **Four-step row deletion gate:** A capability's PySide6 code is deleted in a dedicated PR only after: (1) parity evidence is green, (2) the OS checklist is ticked, and (3) Harbinger signs off.
4. **Spike go/no-go rule (#887–#893):** Feasibility spikes are decided by Harbinger on Grok's review; a no-go records a bounded exception in `migration/features.toml` keeping that PySide6 row alive without re-scoping the architecture.
5. **Coexistence packaging (#886):** While both shells ship, both the PyInstaller build and Tauri bundle share the single installed Python backend environment per machine, and the supervisor launches the sidecar from it. Once the final Qt row is deleted (#921), `ImageToolkit.spec` is retired in favor of a single Tauri installer with a frozen sidecar.

## Consequences

- Every route and `gui/src/` file is accounted for in `migration/features.toml`.
- PySide6 code is never removed without automated differential proof and explicit human sign-off.
