# stack/eslint/

Flat ESLint config for `docs/website`. The root `eslint.config.js` re-exports this file (same
pattern as `stack/nuxt/` and `stack/next/`) so tooling that expects a root-level config still
works, while the actual config lives under `stack/` alongside the other non-primary-framework
tooling this package carries.

```bash
npm run lint   # eslint -c stack/eslint/eslint.config.js .
```
