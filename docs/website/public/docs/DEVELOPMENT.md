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

## Submodules (Absorbed)

The submodules are fully absorbed in-tree (W0-03 #867): Anime-Stitch-Pipeline (`submodules/ASP`), Cel-Shaded-Generator (`submodules/CSG`), Content-Recommendation-Engine (`submodules/CRE`), and Hybrid-Image-Editor (`submodules/HIE`). No `git submodule update` is needed; all code is checked directly into the repository.

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
