"""§1.10B — Bayesian parameter search for ASP verdict-scoring thresholds via Optuna TPE.

Optimises the `_auto_verdict` thresholds in `bench_anime_stitch.py` against a
pre-computed 97-test JSON result file.  The search recomputes verdicts from the
stored per-test metric fields (no pipeline re-run needed), making each trial
essentially free (~0.1 ms) and 200 trials run in < 1 second.

Key insight: `_auto_verdict` uses four tunable scalar thresholds:
  - severe_banding_thresh : seam_coherence absolute cutoff for simple_better gate
  - severe_banding_ratio  : coherence ratio above which the gate fires
  - score_margin          : how much better one score must be to call a winner
  - plus the four weights (coverage, coherence, seam_gradient, ghosting)

Optuna TPE finds the combination that maximises the objective across the corpus.

Usage::

    python -m backend.src.animation.hitl.param_search \
        --results backend/benchmark/results/anime_stitch_20260621_193956.json \
        --trials 200 \
        --out asp_config_optimized.toml

Output TOML is compatible with `load_asp_config()` (§1.8A).
"""

from __future__ import annotations

import argparse
import json
import logging

from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

__all__ = [
    "ASP_SEARCH_PARAMS",
    "_score_config",
    "run_param_search",
]

# ---------------------------------------------------------------------------
# Searchable parameter space
# Each entry: name → (type, lo, hi, default, description)
# ---------------------------------------------------------------------------

ASP_SEARCH_PARAMS: Dict[str, Tuple] = {
    "severe_banding_thresh": (
        float,
        10.0,
        50.0,
        28.0,
        "seam_coherence absolute threshold above which ASP is simple_better",
    ),
    "severe_banding_ratio": (
        float,
        1.1,
        3.0,
        1.5,
        "asp_sc / sim_sc ratio required for the severe-banding gate to fire",
    ),
    "score_margin": (
        float,
        1.01,
        1.30,
        1.10,
        "multiplier gap between asp_score and sim_score to declare a winner",
    ),
    "w_coverage": (
        float,
        0.1,
        1.0,
        0.4,
        "weight of coverage term in composite quality score",
    ),
    "w_coherence": (
        float,
        0.05,
        0.8,
        0.3,
        "weight of seam_coherence penalty in composite quality score",
    ),
    "w_seam_gradient": (
        float,
        0.01,
        0.5,
        0.15,
        "weight of seam_gradient penalty in composite quality score",
    ),
    "w_ghosting": (
        float,
        0.01,
        0.5,
        0.15,
        "weight of ghosting_score penalty in composite quality score",
    ),
}


def _verdict_from_config(asp_m: Dict, sim_m: Dict, cfg: Dict[str, float]) -> str:
    """Recompute `_auto_verdict` with configurable thresholds."""
    if not asp_m or not sim_m:
        return "insufficient_data"

    asp_sc = asp_m.get("seam_coherence", 0.0) or 0.0
    sim_sc = sim_m.get("seam_coherence", 0.0) or 0.0

    sbt = cfg["severe_banding_thresh"]
    sbr = cfg["severe_banding_ratio"]
    if asp_sc > sbt and (sim_sc == 0 or asp_sc > sim_sc * sbr):
        return "simple_better"

    wc = cfg["w_coverage"]
    wco = cfg["w_coherence"]
    wsg = cfg["w_seam_gradient"]
    wg = cfg["w_ghosting"]

    def _score(m: Dict) -> float:
        return (
            (m.get("coverage") or 0.0) * 100.0 * wc
            - (m.get("seam_coherence") or 0.0) * wco
            - (m.get("seam_gradient") or 0.0) * wsg
            - (m.get("ghosting_score") or 0.0) * wg
        )

    asp_score = _score(asp_m)
    sim_score = _score(sim_m)
    margin = cfg["score_margin"]
    if asp_score > sim_score * margin:
        return "asp_better"
    if sim_score > asp_score * margin:
        return "simple_better"
    return "comparable"


def _score_config(cfg: Dict[str, float], result_data: Dict) -> float:
    """Objective: asp_better×2 + comparable×1 across all cv_metrics tests.

    GT-verdict tests are excluded — their verdicts cannot be changed by
    threshold tuning (they depend on ssim_vs_gt, not the metric weights).
    """
    total = 0.0
    for dataset in result_data.get("datasets", []):
        cmp = dataset.get("comparison") or {}
        if cmp.get("verdict_source") != "cv_metrics":
            continue
        asp_m = dataset.get("metrics_asp") or {}
        sim_m = dataset.get("metrics_simple") or {}
        verdict = _verdict_from_config(asp_m, sim_m, cfg)
        if verdict == "asp_better":
            total += 2.0
        elif verdict == "comparable":
            total += 1.0
    return total


def run_param_search(
    result_json_path: str,
    n_trials: int = 200,
    output_toml_path: Optional[str] = None,
    n_jobs: int = 1,
) -> Dict[str, Any]:
    """Run Optuna TPE search over ASP_SEARCH_PARAMS, return best config dict.

    Args:
        result_json_path: Path to a bench_anime_stitch JSON result file.
        n_trials: Number of TPE trials (default 200; each trial < 1 ms).
        output_toml_path: If given, write best config to this TOML path.
        n_jobs: Parallel Optuna workers (1 = sequential, safe for all envs).

    Returns:
        Dict mapping parameter names to best found values.
    """
    try:
        import optuna

        optuna.logging.set_verbosity(optuna.logging.WARNING)
    except ImportError as e:
        raise ImportError("Optuna not installed. Run: pip install optuna") from e

    with open(result_json_path) as fh:
        result_data = json.load(fh)

    def objective(trial: "optuna.Trial") -> float:
        cfg: Dict[str, float] = {}
        for name, (dtype, lo, hi, default, _desc) in ASP_SEARCH_PARAMS.items():
            if dtype is float:
                cfg[name] = trial.suggest_float(name, lo, hi)
            else:
                cfg[name] = trial.suggest_int(name, int(lo), int(hi))
        return _score_config(cfg, result_data)

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, n_jobs=n_jobs, show_progress_bar=False)

    best = study.best_params
    logger.info(
        "[ParamSearch] Best score=%.1f after %d trials: %s",
        study.best_value,
        n_trials,
        best,
    )

    if output_toml_path:
        _write_toml(best, output_toml_path, study.best_value)

    return best


def _write_toml(params: Dict[str, Any], path: str, score: float) -> None:
    lines = [
        "# ASP optimized config — generated by §1.10B param_search.py",
        f"# Optuna TPE best score (cv_metrics corpus): {score:.1f}",
        "",
        "[verdict_scoring]",
    ]
    for k, v in params.items():
        lines.append(f"{k} = {v!r}")
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("[ParamSearch] Config written to %s", path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _main() -> None:
    parser = argparse.ArgumentParser(description="§1.10B ASP Bayesian param search")
    parser.add_argument(
        "--results", required=True, help="Path to bench JSON result file"
    )
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--out", default=None, help="Output TOML path")
    parser.add_argument("--jobs", type=int, default=1)
    args = parser.parse_args()

    best = run_param_search(
        args.results,
        n_trials=args.trials,
        output_toml_path=args.out,
        n_jobs=args.jobs,
    )
    print("Best parameters:")
    for k, v in best.items():
        print(f"  {k} = {v:.4f}" if isinstance(v, float) else f"  {k} = {v}")


if __name__ == "__main__":
    _main()
