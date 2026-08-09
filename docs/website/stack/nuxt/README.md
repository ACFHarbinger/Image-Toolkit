# stack/nuxt/

Nuxt 3 config pointed at this package's `src/` tree — kept as an alternate, SSR-capable surface
alongside the primary Vite + Vue Router build, the same way `stack/next/` is kept for React.
Not part of the default build/deploy pipeline; reachable only via `npm run nuxt:*`.

```bash
npm run nuxt:dev
npm run nuxt:generate
```
