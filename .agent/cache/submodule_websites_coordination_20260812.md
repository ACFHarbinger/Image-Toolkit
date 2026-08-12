# Submodule Website Coordination — 2026-08-12

## Split

- Gemini created the static introduction sites for ASP, CRE, CSG, and HIE and added the parent Pipeline submodule explorer.
- Chat reviewed the shared contract, deployment paths, and parent-site behavior, then removed a production-breaking local-preview fallback from the Pipeline page.

## Shared contract

Each submodule site lives at `docs/website/`, uses the Image-Toolkit dark optical-lab visual language, presents project capabilities and architecture scope, links to repository documentation, and exposes a persistent link back to `https://acfharbinger.github.io/Image-Toolkit/`.

Submodule GitHub Pages workflows deploy each site under the `/app/` base path. The parent Pipeline page therefore uses the registry URLs in `src/constants/submodules.ts` for both new-tab navigation and embedded previews; it does not assume submodule source directories are available inside the parent Vite production bundle.

## Verification note

The parent Pipeline explorer and the four submodule websites were already committed in the respective repositories before Chat's reconciliation pass. Chat's follow-up is limited to the URL/fallback correction and this coordination record.
