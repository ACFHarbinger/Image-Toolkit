# Developer Onboarding & Local Workflow

This guide covers setting up a local development environment, building the C++ `backend` core and React/Tauri frontend, adding a new capability vertical, and running targeted quality checks.

---

## 1. Prerequisites & Environment Setup

| Tool | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | `middleware/` orchestrator, services, ML pipelines, and `gui/` (managed via `uv` + `.venv`) |
| **C++ Toolchain** | C++17 (GCC 11+ / Clang 14+ / MSVC) + CMake 3.20+ + Ninja | `backend/` `pybind11` extension, SQLCipher engine, `libitk_crypto.so`, Catch2 & HIE solver tests |
| **System Libraries** | OpenCV 4.6+, Eigen 3.4, OpenMP, OpenSSL, SQLCipher, libsodium | Linked by `backend/CMakeLists.txt` (resolved via Pixi `.pixi/envs/default` or system packages) |
| **Node.js & npm** | Node 20 LTS | `frontend/` (React 19 + Vite) and `docs/website/` (documentation portal + Storybook) |
| **Rust** | Stable (1.75+) | `frontend/src-tauri/` Tauri 2 desktop host |
| **`just`** | 1.40+ | Task runner across all workspaces (`just --list`) |

### First-Time Bootstrap

```bash
# 1. Sync Python virtual environment and install workspace packages
just install
source .venv/bin/activate

# 2. Build the unified C++ backend extension (backend.cpython-*.so + libitk_crypto.so)
just build::build-base

# 3. Install Node.js workspace dependencies (frontend + docs/website)
npm ci
```

---

## 2. Repository Layout

```text
Image-Toolkit/
├── backend/                  # C++17 core (pybind11, SQLCipher DB, Vault, ASP/HIE native solvers)
│   ├── include/              # Public C++ headers
│   ├── src/                  # C++ implementation + bindings.cpp
│   ├── tests/                # Catch2 (backend_tests) + HIE solver tests (hie_solver_tests)
│   └── benchmarks/           # Google Benchmark suites (base_benchmarks)
├── contracts/                # Capability JSON Schemas, methods.toml, codegen, CONTRACTS.sha256
├── middleware/               # Python orchestrator & domain services
│   ├── src/
│   │   ├── services/         # Feature services (<feature>/api.py, commands.py, handlers.py)
│   │   ├── supervisor/       # Process supervisor (sidecar, Cloud Jobs daemon, slideshow daemon)
│   │   ├── cloud/            # Cloud Jobs engine (JobSpec, pure reconciler, preflight, cost)
│   │   ├── database/         # Unified SQLCipher schema & additive migrations
│   │   ├── core/             # Thin Python wrappers over C++ backend
│   │   └── models/           # PyTorch ML pipelines (ComfyUI, LoRA, BiRefNet, CLIP)
│   ├── test/                 # Python unit & service parity tests
│   └── validation/           # CI policy gates (LoC, additive migrations, Tauri security, docs)
├── frontend/                 # React 19 + TypeScript + Vite webview & Tauri 2 host
│   ├── src/
│   │   ├── shell/            # Catalog-driven rail, ribbon, inspector, status bar
│   │   ├── eventhub/         # Generated EventHub (snapshot + bounded tail)
│   │   ├── features/         # Isolated feature modules (enforced by eslint-plugin-boundaries)
│   │   └── components/       # Shared UI components (documented in Storybook)
│   └── src-tauri/            # Tauri 2 Rust host & per-window capability ACLs
├── gui/                      # Legacy PySide6 desktop UI (frozen to reviewed bugfixes, W0-20)
├── migration/                # Capability migration ledger (migration/features.toml)
└── docs/                     # MkDocs Material + Vue SPA portal, ADRs (docs/adr/), module docs
```

---

## 3. Running & Building Locally

Always activate the Python virtual environment before running Python or `just` commands:

```bash
source .venv/bin/activate
```

| Workflow | Command |
|---|---|
| **Launch Tauri Desktop Dev** | `npm run dev` (or `npm run start-frontend` for Vite webview alone) |
| **Launch Legacy PySide6 App** | `python middleware/main.py` |
| **Rebuild C++ `backend` Core** | `just build::build-base` |
| **Run Native C++ Unit Tests** | `just test-base-cpp` (runs Catch2 `backend_tests` + `hie_solver_tests`) |
| **Regenerate Bridge Contracts** | `python contracts/generate.py` (check with `python contracts/generate.py --check`) |
| **Lint Python Architecture** | `PYTHONPATH=. lint-imports && ruff check` |
| **Lint Frontend Boundaries** | `npm run lint --workspace=frontend` |
| **Run Frontend Unit Tests** | `npm run test --workspace=frontend` |

> **Resource Rule:** Never run full `pytest` directory suites or multi-hour corpus benchmarks (`bench_anime_stitch.py`) directly on shared development machines without coordinating through the benchmark gate in `AGENTS.md`. For day-to-day verification, run targeted single-file `pytest <path/to/test_file.py> -q`.

---

## 4. Adding or Migrating a Capability (Step-by-Step)

Every feature vertical follows the locked Wave 0 spine (see [ARCHITECTURE.md](ARCHITECTURE.md) and [ADR-0009](adr/0009-command-handler-services-and-enforced-boundaries.md)):

1. **Define the Contract (`contracts/`):**
   - Add or update `contracts/schemas/capability/<feature>.json` and register routes in `contracts/methods.toml`.
   - Run `python contracts/generate.py` to update generated bindings and `contracts/CONTRACTS.sha256`.
2. **Implement the Service (`middleware/src/services/<feature>/`):**
   - Create frozen `@dataclass(frozen=True)` Commands and Results in `commands.py`.
   - Implement `@runtime_checkable` `Protocol` handlers in `handlers.py` and the service facade in `service.py`.
   - Re-export the public surface in `middleware/src/services/<feature>/api.py` (only `api.py` may be imported by external callers).
3. **Build the Tauri View (`frontend/src/features/<feature>/`):**
   - Register the capability route in `frontend/src/shell/catalog.json` and `migration/features.toml`.
   - Call the capability through `HostClient` and subscribe to state updates via `EventHub`. Do not import across sibling `src/features/<other>/` directories (`npm run lint --workspace=frontend`).
4. **Document the Module & Verify Freshness (`docs/modules/<feature>.md`):**
   - Copy [`docs/modules/_template.md`](modules/_template.md) to `docs/modules/<feature>.md`.
   - Record the capability's `Contract Schema` path and `Contract SHA-256` from `contracts/CONTRACTS.sha256`.
   - Run `python middleware/validation/check_docs_freshness.py`.

---

## 5. Documentation Portal & Storybook

The documentation system combines **MkDocs Material** (strict CI validation of nav, links, and docstrings) with the interactive **React/Vue Documentation Portal** (`docs/website/`) and **Storybook** for reusable React components (`frontend/src/components/common/*`).

```bash
# Validate MkDocs Material build in strict mode
uv run mkdocs build --config-file docs/mkdocs.yml --strict

# Validate ADR spine and module README contract hashes
python middleware/validation/check_docs_freshness.py

# Check internal Markdown links
python middleware/scripts/check_links.py

# Launch Storybook locally for React component library (port 6006)
npm run storybook --workspace=docs/website

# Build static Storybook bundle + interactive docs portal
npm run build --workspace=docs/website
```

See [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md) and [docs/website/APP.md](website/APP.md) for formatting and docstring conventions.
