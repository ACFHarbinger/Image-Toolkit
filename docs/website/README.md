# docs/website/

Vite + Vue 3 + TypeScript documentation portal and interactive engineering hub for
**Image-Toolkit**. Deployed to GitHub Pages from the `gh-pages` branch by
[`.github/workflows/docs.yml`](../../.github/workflows/docs.yml) — this SPA *is* the deployed
docs site; MkDocs (`docs/mkdocs.yml`) stays wired into CI as a strict-mode validation/link-check
step and as the nav's source of truth, but is not itself published.

## What the site is

A single SPA combining:

1. **Engineering hub** (`/`) — interactive panels (module explorer, submodule ecosystem,
   roadmap/benchmarks, framework islands) implemented as Vue SFCs.
2. **Documentation portal** (`/docs/...` and every other route) — every page in
   [`docs/mkdocs.yml`](../mkdocs.yml)'s `nav:` tree, plus a curated set of repo-wide guides,
   rendered from Markdown client-side at request time.
3. **Framework islands** — this site's own chrome is Vue, but it embeds three more frameworks,
   each mounting real functionality (not a placeholder): a statically-rendered **Astro** island
   (a k-NN "vector flow field" visualization), a live **React** island (mounting
   `frontend/src/components/common/*` verbatim — the actual desktop-app components, also
   documented in isolation via **Storybook**), and an **Aurelia 2** island (a k-means
   convergence simulation). See [Notable implementation notes](#notable-implementation-notes).

### Running it locally

```bash
# from the repository root
npm install
npm run docs-website:dev
# http://localhost:5173
```

Or from this package:

```bash
cd docs/website
npm install
npm run dev
```

### Navigating the site

- The **topbar** switches between the engineering hub (logo/brand) and the documentation portal
  (**Documentation**).
- The **sidebar** groups sections from `mkdocs.yml` + `scripts/generate-nav.mjs`'s
  `EXTRA_SECTIONS`.
- **⌘K / Ctrl+K** fuzzy-searches page titles and source paths.
- Doc pages include an **"On this page"** TOC, **prev/next** links, and **Edit on GitHub**.
- **☀️/🌙** theme toggle (persisted in `localStorage`).

### Adding content

- **New docs page:** add the Markdown under `docs/` and list it in
  [`docs/mkdocs.yml`](../mkdocs.yml) `nav:`. Run `npm run site:nav` (or any `dev`/`build`) to
  regenerate the nav.
- **Repo-wide guide outside `docs/`:** add `{ title, source }` under `EXTRA_SECTIONS` in
  [`scripts/generate-nav.mjs`](scripts/generate-nav.mjs).
- **New hub panel:** add a SFC under `src/frameworks/vue/components/hub/`, then register it in
  `src/frameworks/vue/views/HomeView.vue`.
- **New Storybook story:** add a `*.stories.tsx` under `stories/`, importing the real component
  from `frontend/src/components/common/` (no copies).

## How the app is built

| Path | Role |
| --- | --- |
| `index.html` | Entry HTML + GitHub Pages SPA redirect restore script |
| `public/404.html` | SPA fallback for deep links on GitHub Pages |
| `vite.config.ts` | `SITE_BASE`, React plugin scoped to `frameworks/react/**`, `server.fs.allow` for repo-root Markdown + `frontend/src` |
| `postcss.config.js` / `tailwind.config.js` | Tailwind (scoped to the React island; `preflight` off so it doesn't fight the Vue chrome's hand-written theme) + Autoprefixer |
| `scripts/generate-nav.mjs` | Builds `src/nav.generated.ts` from `mkdocs.yml` + extras |
| `scripts/fix-api-links.mjs` | Rewrites TypeDoc's relative markdown links into router-absolute paths after `gen:api` |
| `typedoc.json` | TypeDoc + `typedoc-plugin-markdown` config → `docs/api/typescript/` (from `frontend/src/math/`) |
| `astro.config.mjs` | Astro island → `public/astro-island/` |
| `.storybook/` | Storybook (`@storybook/react-vite`) → `public/storybook/`, documenting `frontend/src/components/common/*` |
| `src/main.ts` | App bootstrap (Vuex, custom directives, Tailwind + theme CSS) |
| `src/router.ts` | Routes: `/` hub, catch-all docs |
| `src/styles/` | Tailwind entry, theme tokens, markdown, hub CSS |
| `src/composables/` | Docs loading, Markdown pipeline, theme |
| `src/configs/`, `constants/`, `enums/`, `interfaces/` | Hub tunables, module/roadmap/benchmark/submodule data, shared types |
| `src/hooks/`, `utils/` | Reduced-motion hook, shared formatters |
| `src/graphql/` | Docs/content GraphQL schema stub (unused by any resolver yet) |
| `src/simulations/` | Framework-neutral k-means convergence generator, driving the Aurelia island |
| `src/libraries/vuex/` | Vuex store (state/mutations/actions/services), persists the active hub tab |
| `src/libraries/form/` | TanStack Vue Form helper |
| `src/libraries/motion/` | Motion variant presets for hub transitions |
| `src/libraries/router/` | Vue Router factory (`createAppRouter`) |
| `src/frameworks/vue/App.vue` | Shell layout wrapper (topbar / sidebar) |
| `src/frameworks/vue/views/` | `HomeView` (hub) and `DocPage` (Markdown portal) |
| `src/frameworks/vue/directives/` | Custom Vue directives (`v-click-outside`, `v-focus`, `v-intersect`) |
| `src/frameworks/vue/components/` | Shell chrome + `hub/` interactive panels |
| `src/frameworks/astro/` | Astro island source (`VectorFlowField.astro`) + Vue iframe wrapper |
| `src/frameworks/react/` | `ComponentGallery.tsx`, importing `frontend/src/components/common/*` directly |
| `src/frameworks/aurelia/` | `ann-convergence-app.ts` custom element + `mount.ts` + Vue wrapper |
| `src/frameworks/shared/` | Framework-neutral island lifecycle logging |
| `public/astro-island/` | Prebuilt Astro static island (from `npm run build:astro`) |
| `public/storybook/` | Prebuilt Storybook static site (from `npm run build-storybook`) |
| `nuxt.config.ts` / `next.config.js` / `eslint.config.js` | Re-exports from `stack/{nuxt,next,eslint}/` |

### Build / deploy

```bash
npm run build                 # from repo root workspace
# or
cd docs/website && npm run build

SITE_BASE=/Image-Toolkit/ npm run build   # production subpath (matches project-page deploy)
```

`prebuild` regenerates the nav, generates the TypeScript API reference (TypeDoc), builds the
Astro island, and builds the Storybook static site — all before `vite build` runs. Production CI
(`.github/workflows/docs.yml`) runs this and publishes `docs/website/dist/` to `gh-pages`.

### Project layout

```
docs/website/
├── index.html
├── eslint.config.js / nuxt.config.ts / next.config.js   # re-export → stack/
├── typedoc.json                # → docs/api/typescript/
├── astro.config.mjs            # Astro island → public/astro-island
├── .storybook/                 # → public/storybook
├── stories/                    # Storybook stories for frontend/src/components/common/*
├── public/
├── stack/
│   ├── eslint/, nuxt/, next/
├── vite.config.ts
├── scripts/{generate-nav,fix-api-links}.mjs
└── src/
    ├── main.ts, router.ts, nav.generated.ts (AUTO-GENERATED)
    ├── styles/, composables/
    ├── configs/, constants/, enums/, interfaces/, hooks/, utils/
    ├── graphql/, simulations/
    ├── libraries/{form,motion,router,vuex}
    └── frameworks/
        ├── vue/       (primary — App.vue, views/, components/, directives/)
        ├── astro/     (island — VectorFlowField.astro)
        ├── react/     (island — ComponentGallery.tsx)
        ├── aurelia/   (island — ann-convergence-app.ts)
        └── shared/    (framework-neutral helpers)
```

## Notable implementation notes

- **`nav.generated.ts` is not hand-edited** — regenerated on every `predev` / `prebuild`.
- **`useDocs.ts`** bundles `docs/**/*.md` via `import.meta.glob`; `resolveKey()` handles the
  `docs/` prefix collapse for sources nested inside `docs/`.
- **MkDocs stays CI-validation-only** — `docs.yml` runs `mkdocs build --strict` to catch broken
  nav entries/links, but only `docs/website/dist/` is published to `gh-pages`.
- **Islands are real, not placeholders** — the Astro flow-field, the React component gallery,
  and the Aurelia convergence sim all do genuine work; see [`APP.md`](APP.md) for the rationale.
- **`src/frameworks/react/`** imports `frontend/src/components/common/*` directly (no copy) —
  `vite.config.ts`'s `server.fs.allow` and the `@vitejs/plugin-react` scoping make that work.
- **Tailwind exists only for the React island** (`corePlugins.preflight: false`) — the Vue chrome
  is styled entirely through `src/styles/theme.css`'s CSS custom properties.

## Tooling packages (`stack/`)

| Directory | Role |
| --- | --- |
| [`stack/eslint/`](stack/eslint/) | Flat ESLint config; root `eslint.config.js` re-exports it |
| [`stack/nuxt/`](stack/nuxt/) | Alternate SSR-capable Nuxt 3 surface over `src/` |
| [`stack/next/`](stack/next/) | Alternate Next.js surface over `src/frameworks/react/` |

```bash
npm run lint

npm run nuxt:dev
npm run next:dev
```
