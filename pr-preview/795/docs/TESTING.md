# Testing

## Python

```bash
source .venv/bin/activate
pytest
# or domain-specific:
just test  # see just help for language modules
```

## ASP quality suite

```bash
just asp-benchmark-verify   # five-test structural suite
just asp-benchmark-first 5  # quick smoke
just asp-benchmark-assess   # human coherence ratings (not automated)
```

Automated metrics do **not** replace human structural-coherence judgment for panoramas. See [BENCHMARKS.md](BENCHMARKS.md) and ASP research notes under `docs/moon/` / the ASP submodule.

## Frontend / docs website

```bash
cd docs/website
npm test
npm run lint
```

## C++ base

```bash
just build-base
# ctest under base/build when enabled
```
