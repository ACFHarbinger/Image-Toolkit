"""The bench script must alias the absorbed stitching package.

``just asp-benchmark-verify`` executes ``bench_anime_stitch.py`` by path.
The pre-move ``parents[1] / "src"`` alias is not a package after the move
into ``middleware/benchmark/asp/``.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from middleware.benchmark.asp.bootstrap import (
    load_benchmark_aliases,
    repo_root,
    stitching_src,
)


def test_stitching_src_is_the_absorbed_package():
    src = stitching_src()
    assert src == repo_root() / "middleware" / "src" / "stitching"
    assert (src / "core" / "pipeline" / "run_stage.py").is_file()
    bench = repo_root() / "middleware" / "benchmark" / "asp" / "bench_anime_stitch.py"
    stale = bench.resolve().parents[1] / "src"
    assert stale != src
    assert not stale.is_dir()


def test_install_asp_backend_in_a_fresh_interpreter():
    bootstrap = repo_root() / "middleware" / "benchmark" / "asp" / "bootstrap.py"
    code = (
        "import importlib.util\n"
        "from pathlib import Path\n"
        f"spec = importlib.util.spec_from_file_location('bootstrap', {str(bootstrap)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "src = mod.install_asp_backend()\n"
        "import asp_backend\n"
        "assert Path(asp_backend.__file__).resolve().parent == src.resolve()\n"
        "from asp_backend.core.pipeline._frame_utils import edgeless_compose_enabled, "
        "edgeless_reproposal_enabled\n"
        "assert edgeless_compose_enabled() is False\n"
        "assert edgeless_reproposal_enabled() is True\n"
    )
    env = os.environ.copy()
    env.pop("ASP_EDGELESS_COMPOSE", None)
    env.pop("ASP_EDGELESS_REPROPOSAL", None)
    env["PYTHONPATH"] = str(repo_root()) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr


def test_bench_module_exposes_missing_dataset_check():
    bench_path = repo_root() / "middleware" / "benchmark" / "asp" / "bench_anime_stitch.py"
    spec = importlib.util.spec_from_file_location("bench_anime_stitch_bootstrap", bench_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.missing_requested_datasets(
        ["asp_test04", "asp_test08"],
        [],
    ) == ["asp_test04", "asp_test08"]
    assert module.missing_requested_datasets(
        ["asp_test04"],
        ["/tmp/asp_test04"],
    ) == []
    # Alias load is idempotent once this process already imported stitching.
    assert load_benchmark_aliases() == stitching_src()
    assert Path(module.__file__).name == "bench_anime_stitch.py"
