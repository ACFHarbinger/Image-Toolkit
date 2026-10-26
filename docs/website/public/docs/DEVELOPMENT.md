# Development

How to set up and work on Image-Toolkit locally.

## Prerequisites

- Python 3.11+ with project `.venv` (`just install` / `uv sync`)
- Node.js LTS (docs website + frontend)
- Optional: CUDA GPU for full ASP ML benchmark runs
- `just` command runner

## Common commands

```bash
just help                 # all recipes
just install              # dependencies
just build-all            # C++ base + Kotlin + frontend
just check                # Rust / type checks where applicable
just asp-benchmark-assess # human coherence rating inspector (ASP)
just benchmark-dashboard  # Streamlit IT performance dashboard
```

## Absorbed Modules

The previous external submodules are fully absorbed into the monorepo (W0-03 #867/#1039): Anime-Stitch-Pipeline (`middleware/src/stitching`, `backend/src/asp`), Cel-Shaded-Generator (`middleware/src/csg`), Content-Recommendation-Engine (`middleware/src/cre`), and Hybrid-Image-Editor (`middleware/src/hie`, `backend/src/hie`). No `git submodule update` is needed; all code is checked directly into the monorepo.

## Documentation website

```bash
cd docs/website
npm install
npm run dev     # Vite dev server
npm run build
```

See [DOCUMENTATION_STANDARDS.md](DOCUMENTATION_STANDARDS.md) and [docs/website/README.md](website/README.md).

## Human ASP ratings

After benchmark outputs exist under `dump/` (or your configured data dir):

```bash
just asp-benchmark-assess
```

Ratings write to `data/benchmarks/asp_evaluations_YYYYMMDD.json` by default.
