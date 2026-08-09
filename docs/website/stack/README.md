# stack/

Tooling packages for `docs/website`. Each root-level config re-exports from here (`eslint.config.js`,
`nuxt.config.ts`, `next.config.js`) so tools that expect a root config keep working, while the
actual configuration is grouped by concern under `stack/`.

| Directory | Role |
| --- | --- |
| [`eslint/`](eslint/) | Flat ESLint config covering `.ts`/`.tsx`/`.vue` |
| [`nuxt/`](nuxt/) | Alternate SSR-capable Nuxt 3 surface over `src/` (not part of the default build) |
| [`next/`](next/) | Alternate Next.js surface over `src/frameworks/react/` (not part of the default build) |
