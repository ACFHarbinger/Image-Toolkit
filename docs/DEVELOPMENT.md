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

## Submodules

Anime-Stitch-Pipeline lives at `submodules/ASP` (path short name; remote still Anime-Stitch-Pipeline). Content-Recommendation-Engine is `submodules/CRE`; Cel-Shaded-Generator is `submodules/CSG`.

```bash
git submodule update --init --recursive
```

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
