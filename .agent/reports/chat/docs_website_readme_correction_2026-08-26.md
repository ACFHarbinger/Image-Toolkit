# Documentation website README correction — 2026-08-26

Corrected `docs/website/README.md` to describe the active React 19 + Vite SPA:
`src/main.tsx`, `App.tsx`, page routes, static Markdown assets, build command,
and the boundary between the active shell and retained migration/experimental
framework directories.

Validation was attempted with `npm run build`. It is currently blocked before
TypeScript because dependencies are absent and the root lockfile is stale:
`lucide-react@1.31.0` in `package-lock.json` does not satisfy the workspace
manifest's `lucide-react@1.34.0`. No lockfile was modified. Resolve that
pre-existing lock drift, run `npm install`, then rerun the website build.
