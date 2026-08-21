#!/usr/bin/env python3
"""Thin compatibility shim for the ASP human-rating dispatcher.

Historically this lived at ``backend/controllers/bench_eval_dispatch.py`` in
the monorepo. After Anime-Stitch-Pipeline moved to ``submodules/ASP``, the
real implementation is::

    submodules/ASP/backend/src/cli/eval_dispatch.py

Root recipes should prefer that path (see ``tools/benchmark/justfile``).
This shim remains so older docs/scripts that still invoke the controllers
path keep working.

Usage (from Image-Toolkit root)::

    just asp-benchmark-assess
    python backend/controllers/bench_eval_dispatch.py --help
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main() -> None:
    it_root = Path(__file__).resolve().parents[2]
    asp_dispatch = (
        it_root / "submodules" / "ASP" / "backend" / "src" / "cli" / "eval_dispatch.py"
    )
    if not asp_dispatch.is_file():
        raise SystemExit(
            f"ASP eval_dispatch not found at {asp_dispatch}. "
            "Initialize the submodules/ASP git submodule."
        )
    # Ensure both roots are importable when this shim is the entry script.
    for p in (str(it_root), str(it_root / "submodules" / "ASP")):
        if p not in sys.path:
            sys.path.insert(0, p)
    sys.argv[0] = str(asp_dispatch)
    runpy.run_path(str(asp_dispatch), run_name="__main__")


if __name__ == "__main__":
    main()
