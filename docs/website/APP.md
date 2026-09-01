# Why this site looks the way it does

`docs/website/` is deliberately more than a documentation static-site generator. It exists to do
two things at once: serve as Image-Toolkit's actual documentation portal, and serve as a working
demonstration of multi-framework interop patterns — because Image-Toolkit itself is a genuinely
polyglot project (Python, C++, Kotlin, Swift, TypeScript/React, Rust archive), and the docs site
mirrors that reality instead of hiding it behind a single framework.

## History

This package existed once before, was removed on 2026-08-07 ("consolidate documentation
toolchains", citing an upstream ASP-repo backlog issue), and was rebuilt from scratch here —
this time with the full feature set intended from the start, rather than the earlier partial
build. See `docs/moon/CHANGELOG.md` for both entries.

## Why React as the primary shell

The chrome, documentation renderer, and engineering hub use React + Vite, matching the
desktop frontend. The former Vue portal was removed so the deployed site has one primary UI
runtime and one router.

## Why framework islands

Three deliberate, non-trivial islands live under `src/frameworks/`, each demonstrating a
different integration mechanic:

- **Astro** (`frameworks/astro/`) — a build-time static-rendered SVG visualization
  (`VectorFlowField.astro`), compiled standalone via `astro build` into
  `public/astro-island/index.html`, then embedded as a themed iframe. Demonstrates the
  "prebuilt static island" pattern — zero client-side framework runtime for content that never
  needs to be interactive beyond a hover/reveal.
- **React** (`frameworks/react/`) — `ComponentGallery.tsx` imports Image-Toolkit's *real*
  `frontend/src/components/common/*` components directly (no port, no copy) and mounts them via
  React page. Demonstrates the "live client-side mount"
  pattern, and doubles as a way to sanity-check those shared components render correctly outside
  the desktop app's own Electron/Tauri shell. The same components are documented in isolation via
  Storybook (`stories/`), built standalone into `public/storybook/`.
- **Aurelia 2** (`frameworks/aurelia/`) — `ann-convergence-app.ts`, a real Aurelia custom element
  with bindable state, a repeat.for-driven SVG render, and its own play/pause/reset lifecycle,
  mounted via `Aurelia.app({ host, component }).start()`. Demonstrates a framework whose own
  component model (custom elements, binding commands) is independent of React.

Each island is real, working functionality tied to something true about Image-Toolkit — not a
placeholder swapped in to tick a box:

- The Astro flow-field visualizes k-nearest-neighbor search, the conceptual shape of the
  pgvector-backed similarity search in `backend/src/database/image_database.py`.
- The React gallery *is* the desktop app's actual UI kit.
- The Aurelia simulation visualizes k-means convergence, the conceptual shape of building an
  approximate-nearest-neighbor index over a large image library.

## Why MkDocs stays, but only for validation

`docs/mkdocs.yml` remains the single source of truth for the documentation nav tree
(`scripts/generate-nav.mjs` parses it to build `src/nav.generated.ts`) and Sphinx remains for
Python API autodoc (`docs/sphinx/`). But neither is published to GitHub Pages anymore — this SPA
is. `mkdocs build --strict` still runs in CI (`.github/workflows/docs.yml`) purely as a
validation gate: it catches a broken nav entry or dead link before it can silently break this
site's routing, without requiring a second deployed site to keep in sync.

## Why the extra tooling scaffolding (Next and GraphQL schema)

`stack/next/` is an alternate, SSR-capable React surface over the same `src/` tree. It is not
used by the default build, but leaves a starting point if pages need pre-rendering. The GraphQL
schema is a stub for a future documentation/content API; no resolver exists yet.
