# frontend/

**Scaffold — not yet implemented.** A Tauri-based cross-platform desktop UI
for Manga Colorization & Animation, as an alternative to the PySide6 desktop
UI in `../gui/`. Intended to talk to the same `../src/` solvers (Levin
scribble colorization, screentone propagation, optimal transport, graph-cut
temporal coherence, ARAP mesh puppeteering) via a local HTTP/IPC bridge —
not yet wired up.

```
frontend/
  src/            TypeScript/React UI (placeholder: src/main.ts)
  src-tauri/      Rust Tauri shell (placeholder: a no-op window)
```

## Status

This is a directory skeleton, not a working app. Building it out means:

1. Deciding the bridge protocol to `../src/` (REST via a small FastAPI/
   Flask wrapper around the solver functions, or PyO3 bindings called
   directly from the Tauri Rust shell).
2. Porting the colorization/animation/puppeteering tabs' canvas editor and
   mesh overlay editor (see `../gui/src/elements/`) to React/canvas
   components.
3. Wiring `npm run tauri dev` / `tauri build` for desktop packaging.

## Local dev (once implemented)

```bash
cd frontend
npm install
npm run tauri dev
```
