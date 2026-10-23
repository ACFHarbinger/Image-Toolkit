# PR #976 runtime and event fixes

- Stage the uv-managed standalone Python distribution (interpreter, standard library and shared libraries), dereference links, overlay venv dependencies, and include middleware plus the canonical contracts directory. Validate relocated interpreter prefix and sidecar catalog construction before replacing an existing bundle. Reject system Python prefixes instead of pretending a copied venv is portable.
- Resolve the bundled `python/bin/python3`; remove inherited PYTHONHOME and avoid a nonexistent VIRTUAL_ENV. Keep checkout discovery for development.
- Forward sidecar event frames through `bridge-event`; RustTransport exposes onEvent, waits for subscription readiness before sending, and detaches on close even during registration. Shell effect setup owns a fresh client so StrictMode cleanup cannot permanently close the reused client.

Validation: relocated fixture runtime starts and handshakes after its source tree is removed (1 test); conversion dispatch (6); frontend transport subscription/cleanup (3); Rust bridge routing/runtime/session checks (5). TypeScript, Ruff, contracts freshness and whitespace checks pass. Native Rust compilation used two jobs.

The relocation test uses an empty dependency venv and the actual standalone Python distribution; it proves independent Python/catalog startup, not all native/ML dependencies on another OS. A full production bundle installation, interactive desktop event delivery, Windows/macOS packaging, full suites and benchmarks were not run.
