# Documentation website

The deployed documentation site is a React 19 + Vite single-page application.
It combines the public engineering hub with a client-side Markdown reader for
the selected documents in `public/docs/`. MkDocs remains a separate
strict-validation path for the repository documentation; it is not this app's
runtime shell.

## Run and build

```bash
cd docs/website
npm install
npm run dev
npm run build
```

Set `SITE_BASE=/Image-Toolkit/` for a project-page deployment. Vite writes the
production application to `dist/`.

## Active application structure

| Path | Purpose |
| --- | --- |
| `src/main.tsx` | React bootstrap and global styles |
| `src/App.tsx` | Router, shared HUD navigation, and page routes |
| `src/pages/` | Home, Journal, Quality dashboard, Pipeline, and Docs pages |
| `src/components/` | Shared visual components, including the 2D/3D hero and pipeline view |
| `src/styles/`, `src/App.css`, `src/index.css` | Design tokens, Markdown styling, and HUD chrome |
| `public/docs/` | Markdown documents fetched by the Docs route |
| `scripts/` | Static dashboard-data and M0-data generation helpers |
| `vite.config.ts` | React plugin, deploy base, repository-source access, and output settings |

Routes are `/`, `/journal`, `/dashboard`, `/pipeline`, and `/docs`; the Docs
route also accepts a document filename, for example `/docs/ARCHITECTURE.md`.

## Design and scope

The site uses the Optic Lab visual system: a readable body face with Chakra
Petch display treatment, cyan/violet/magenta HUD accents, panel chrome, and
motion that remains additive to the content. The quality dashboard and journal
present evidence; they do not turn proxy metrics into acceptance decisions.

`src/frameworks/` and `stack/` contain migration/experimental integrations.
They are not the active application shell. Keep new site pages and shared
chrome in the React paths above unless a separately approved integration needs
one of those surfaces.

## Documentation content

To add a document exposed by the current React reader, place its built Markdown
asset in `public/docs/` and add it to `DOC_PAGES` in `src/pages/Docs.tsx`.
Repository Markdown and MkDocs navigation remain maintained under `docs/` and
`docs/mkdocs.yml`; keep both sources aligned when publishing a new guide.
