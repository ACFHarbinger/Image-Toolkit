# docs/website/

A Vue 3 + Vite single-page site that renders every `docs/**/*.md` (and
`docs/**/*.ipynb`) file directly — no separate content pipeline. Deployed to
GitHub Pages from the `gh-pages` branch by `.github/workflows/docs.yml`.

## How it works

- `scripts/generate-nav.mjs` parses `../mkdocs.yml`'s `nav:` tree (the single
  source of truth for site structure — shared with the mkdocs/Material
  build) into `src/nav.generated.ts`. Runs automatically before `dev`/`build`.
- `src/composables/useDocs.ts` bundles every markdown/notebook file under
  `docs/` via `import.meta.glob`, lazily loaded per route.
- `src/composables/useMarkdown.ts` renders markdown with `markdown-it`
  (syntax highlighting via `highlight.js`, Mermaid diagrams rendered live).
- Routing is a single catch-all route (`src/views/DocPage.vue`) that resolves
  the URL against the generated nav index.

## Local dev

```bash
cd docs/website
npm install
npm run dev       # http://localhost:5173
```

## Build

```bash
npm run build      # -> dist/
npm run preview    # serve dist/ locally
```

Set `GITHUB_PAGES=1` when building for the `gh-pages` deployment so asset
URLs are prefixed with `/Image-Toolkit/` to match the Pages subpath.

## Adding a page

Add the markdown file wherever it belongs under `docs/`, then add an entry
to `docs/mkdocs.yml`'s `nav:` — both the mkdocs/Material portal and this
site pick it up automatically on the next build.
