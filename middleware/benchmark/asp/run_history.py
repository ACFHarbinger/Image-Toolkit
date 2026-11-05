"""Archive of past benchmark runs, so ASP can be compared with its own
previous versions as well as with OpenCV / Overmix / Hugin.

The bench overwrites ``panorama.png`` and ``output/*_anime_stitch.png`` on
every run. Each run is therefore also archived under
``<results dir>/runs/<run id>/``::

    run.json              git sha/dirty, label, slice, ASP_* env, cases, status
    code.patch            ``git diff HEAD`` when the tree was dirty
    <case>/asp.png        published ASP output
    <case>/raw_asp.png    Raw ASP composite, when one exists
    <case>/opencv.png     the OpenCV SCANS output that run compared against
    <case>/result.json    the bench result row (metrics, GT scores, timings)

Images are hard links into ``runs/.blobs/`` (content addressed), so an
unchanged output costs no extra space across runs.

CLI::

    python middleware/benchmark/asp/run_history.py list
    python middleware/benchmark/asp/run_history.py compare [--run ID] [--prev ID]
    python middleware/benchmark/asp/run_history.py rescore [--run ID | --all]

``rescore`` recomputes the fair GT scores of archived outputs with the
current ``fair_gt.py`` (cached per image content and metric version), so
runs stay comparable when the metric changes.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

_IMAGES = (
    ("asp.png", "anime_path"),
    ("raw_asp.png", "raw_asp_path"),
    ("opencv.png", "simple_path"),
)
_REPO = Path(__file__).resolve().parents[3]


def history_root() -> Path:
    """``ASP_BENCH_HISTORY_DIR``, else ``<bench results dir>/runs``."""
    env = os.environ.get("ASP_BENCH_HISTORY_DIR")
    if env:
        return Path(env).expanduser()
    base = os.environ.get(
        "ASP_BENCH_RESULTS_DIR", str(Path.home() / "Downloads/Data/Tests/asp-benchmark")
    )
    return Path(base).expanduser() / "runs"


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=_REPO, capture_output=True, text=True, timeout=10, check=False
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _write_json(path: Path, value) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def new_run(
    cases: list[str], *, label: str | None = None, slice_name: str | None = None,
    root: Path | None = None,
) -> Path:
    """Create ``runs/<id>/run.json``; returns the run directory."""
    root = root or history_root()
    now = datetime.datetime.now()
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") if label else ""
    run_id = now.strftime("%Y%m%d-%H%M%S") + (f"-{slug}" if slug else "")
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    _write_json(run_dir / "run.json", {
        "run_id": run_id,
        "created": now.isoformat(timespec="seconds"),
        "label": label,
        "slice": slice_name,
        "cases": list(cases),
        "git": {
            "sha": _git("rev-parse", "HEAD"),
            "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(_git("status", "--porcelain", "--untracked-files=no")),
        },
        "env": {k: v for k, v in sorted(os.environ.items()) if k.startswith("ASP_")},
        "status": "running",
    })
    patch = _git("diff", "HEAD")  # uncommitted changes; the sha alone is not enough
    for f in _git("ls-files", "--others", "--exclude-standard", "--", "middleware/*.py").splitlines():
        patch += "\n" + _git("diff", "--no-index", "--", "/dev/null", f)
    if patch:
        (run_dir / "code.patch").write_text(patch + "\n", encoding="utf-8")
    return run_dir


def _store(src: str, dst: Path, blobs: Path) -> None:
    digest = hashlib.sha256(Path(src).read_bytes()).hexdigest()[:24]
    blob = blobs / f"{digest}{Path(src).suffix or '.png'}"
    if not blob.exists():
        blobs.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, blob)
    if dst.exists():
        dst.unlink()
    try:
        os.link(blob, dst)
    except OSError:  # other filesystem
        shutil.copy2(blob, dst)


def archive_case(run_dir: Path, row: dict) -> Path:
    """Copy one dataset's outputs and result row into the run."""
    case_dir = run_dir / str(row["name"])
    case_dir.mkdir(parents=True, exist_ok=True)
    for fname, key in _IMAGES:
        src = row.get(key)
        if src and os.path.isfile(src):
            _store(src, case_dir / fname, run_dir.parent / ".blobs")
    _write_json(case_dir / "result.json", row)
    return case_dir


def finish_run(run_dir: Path, *, status: str = "done", results_json: str | None = None) -> None:
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    meta.update(status=status, finished=datetime.datetime.now().isoformat(timespec="seconds"))
    if results_json:
        meta["results_json"] = results_json
    _write_json(run_dir / "run.json", meta)


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    path: Path
    meta: dict

    def cases(self) -> list[str]:
        return sorted(p.name for p in self.path.iterdir() if (p / "result.json").is_file())

    def has(self, case: str) -> bool:
        return (self.path / case / "result.json").is_file()

    def image(self, case: str, fname: str = "asp.png") -> Path | None:
        p = self.path / case / fname
        return p if p.is_file() else None

    def result(self, case: str) -> dict:
        p = self.path / case / "result.json"
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}


def list_runs(root: Path | None = None) -> list[RunInfo]:
    """Every archived run, oldest first."""
    root = root or history_root()
    if not root.is_dir():
        return []
    runs = []
    for d in sorted(root.iterdir()):
        if d.name.startswith(".") or not (d / "run.json").is_file():
            continue
        try:
            meta = json.loads((d / "run.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        runs.append(RunInfo(d.name, d, meta))
    return runs


def resolve_run(spec: str | None, root: Path | None = None) -> RunInfo | None:
    """``None``/``"latest"`` → newest run; else a run id, id prefix, label or path."""
    runs = list_runs(root)
    if not runs:
        return None
    if spec in (None, "", "latest"):
        return runs[-1]
    p = Path(spec).expanduser()
    if (p / "run.json").is_file():
        return RunInfo(p.name, p, json.loads((p / "run.json").read_text(encoding="utf-8")))
    hits = (
        [r for r in runs if r.run_id == spec]
        or [r for r in runs if r.run_id.startswith(spec)]
        or [r for r in runs if r.meta.get("label") == spec]  # newest run with that label
    )
    return hits[-1] if hits else None


def previous_run(case: str, before: RunInfo, root: Path | None = None) -> RunInfo | None:
    """Newest run older than ``before`` that has ``case``."""
    older = [r for r in list_runs(root) if r.run_id < before.run_id and r.has(case)]
    return older[-1] if older else None


def _gt(row: dict, key: str, field: str = "fair_ssim_vs_gt") -> float | None:
    return ((row.get("ground_truth") or {}).get(key) or {}).get(field)


def _combined(row: dict, key: str) -> float | None:
    """SSIM x GT coverage: uncovered GT counts as a miss, so a tight crop
    is not rewarded (asp_test46: OpenCV covers 49% of the GT, ASP 98%)."""
    s, c = _gt(row, key), _gt(row, key, "fair_cov_vs_gt")
    return None if s is None or c is None else round(s * c, 4)


def compare(run: RunInfo, prev: RunInfo | None = None, root: Path | None = None) -> list[dict]:
    """Per-case fair GT SSIM: ASP (this run), ASP (previous), and comparators."""
    rows = []
    for case in run.cases():
        cur = run.result(case)
        p = prev if prev is not None and prev.has(case) else (
            None if prev is not None else previous_run(case, run, root)
        )
        rows.append({
            "case": case,
            "asp": _gt(cur, "metrics_asp"),
            "asp_prev": _gt(p.result(case), "metrics_asp") if p else None,
            "prev_run": p.run_id if p else None,
            "opencv": _gt(cur, "metrics_simple"),
            "overmix": _gt(cur, "metrics_overmix"),
            "hugin": _gt(cur, "metrics_hugin"),
            "identity": cur.get("result_identity"),
            "registration": (cur.get("registration_route") or {}).get("selected"),
            "combined": {
                "asp": _combined(cur, "metrics_asp"),
                "asp_prev": _combined(p.result(case), "metrics_asp") if p else None,
                "opencv": _combined(cur, "metrics_simple"),
                "overmix": _combined(cur, "metrics_overmix"),
                "hugin": _combined(cur, "metrics_hugin"),
            },
        })
    return rows


_GT_KEYS = (
    ("metrics_asp", "asp.png", None),
    ("metrics_simple", "opencv.png", None),
    ("metrics_overmix", None, "overmix_stitch.png"),
    ("metrics_hugin", None, "hugin_stitch.png"),
)


def _data_dir() -> Path:
    return Path(os.environ.get("ASP_BENCH_DATA_DIR", "~/Downloads/Data/Dump")).expanduser()


def _find_gt(case: str) -> Path | None:
    for ext in (".png", ".jpg", ".jpeg"):
        p = _data_dir() / "ground_truth" / f"{case}{ext}"
        if p.is_file():
            return p
    return None


def rescore(run: RunInfo, root: Path | None = None) -> int:
    """Recompute fair GT scores for ``run``; returns cases updated."""
    import cv2

    from middleware.benchmark.asp.fair_gt import FAIR_METRIC_VERSION, fair_gt_score

    root = root or run.path.parent
    cache_path = root / ".fair_cache.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cache = {}
    updated = 0
    for case in run.cases():
        gt_path = _find_gt(case)
        if gt_path is None:
            continue
        row = run.result(case)
        gt_block = row.setdefault("ground_truth", {})
        gt_img = None
        for key, archived, comparator in _GT_KEYS:
            if archived:
                img_path = run.image(case, archived)
            else:
                src = row.get(f"{key.split('_', 1)[1]}_path") or str(
                    _data_dir() / case / "output" / comparator
                )
                img_path = Path(src) if src and Path(src).is_file() else None
            if img_path is None:
                continue
            digest = hashlib.sha256(img_path.read_bytes()).hexdigest()[:24]
            ck = f"v{FAIR_METRIC_VERSION}:{case}:{digest}"
            if ck not in cache:
                if gt_img is None:
                    gt_img = cv2.imread(str(gt_path))
                cache[ck] = fair_gt_score(cv2.imread(str(img_path)), gt_img)
            block = gt_block.setdefault(key, {})
            block["fair_ssim_vs_gt"] = cache[ck]["ssim"]
            block["fair_cov_vs_gt"] = cache[ck]["cov"]
        gt_block["fair_metric_version"] = FAIR_METRIC_VERSION
        _write_json(run.path / case / "result.json", row)
        updated += 1
    _write_json(cache_path, cache)
    return updated


def _fmt(v: float | None) -> str:
    return "   —  " if v is None else f"{v:.4f}"


def _print_compare(run: RunInfo, rows: list[dict]) -> None:
    print(f"run {run.run_id}  ({run.meta.get('label') or 'no label'}, git {run.meta.get('git', {}).get('sha', '')[:9]})")
    print(f"{'case':<12} {'ASP':>7} {'prev':>7} {'Δprev':>7} {'OpenCV':>7} {'ΔCV':>7} {'Overmix':>7} {'Hugin':>7}  poses")
    for r in rows:
        d_prev = r["asp"] - r["asp_prev"] if r["asp"] is not None and r["asp_prev"] is not None else None
        d_cv = r["asp"] - r["opencv"] if r["asp"] is not None and r["opencv"] is not None else None
        print(
            f"{r['case']:<12} {_fmt(r['asp']):>7} {_fmt(r['asp_prev']):>7} "
            f"{'   —  ' if d_prev is None else f'{d_prev:+.4f}':>7} {_fmt(r['opencv']):>7} "
            f"{'   —  ' if d_cv is None else f'{d_cv:+.4f}':>7} {_fmt(r['overmix']):>7} {_fmt(r['hugin']):>7}"
            f"  {r.get('registration') or r.get('identity') or ''}"
        )

    def mean_delta(get, a: str, b: str) -> tuple[float | None, int, int]:
        pairs = [(get(r)[a], get(r)[b]) for r in rows if get(r)[a] is not None and get(r)[b] is not None]
        if not pairs:
            return None, 0, 0
        return sum(x - y for x, y in pairs) / len(pairs), sum(x > y for x, y in pairs), len(pairs)

    for label, get in (("SSIM (shared region)", lambda r: r), ("SSIM x coverage", lambda r: r["combined"])):
        print(label)
        for other in ("asp_prev", "opencv", "overmix", "hugin"):
            m, wins, n = mean_delta(get, "asp", other)
            if m is not None:
                print(f"  ASP vs {other:<8} mean Δ {m:+.4f}  ahead on {wins}/{n}")
    print(f"ASP unscoreable: {sum(r['asp'] is None for r in rows)}/{len(rows)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    c = sub.add_parser("compare")
    c.add_argument("--run", default="latest")
    c.add_argument("--prev", default=None, help="run id; default: per case, the newest older run")
    c.add_argument("--json", action="store_true")
    rs = sub.add_parser("rescore")
    rs.add_argument("--run", default="latest")
    rs.add_argument("--all", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "rescore":
        targets = list_runs() if args.all else [resolve_run(args.run)]
        for r in targets:
            if r is None:
                print(f"No run matches {args.run!r}")
                return 1
            print(f"{r.run_id}: rescored {rescore(r)} cases")
        return 0
    if args.cmd == "list":
        for r in list_runs():
            m = r.meta
            print(f"{r.run_id:<40} {m.get('status', ''):<8} {len(r.cases()):>3} cases  "
                  f"slice={m.get('slice') or '-'}  git={m.get('git', {}).get('sha', '')[:9]}"
                  f"{'+dirty' if m.get('git', {}).get('dirty') else ''}")
        return 0
    run = resolve_run(args.run)
    if run is None:
        print(f"No run matches {args.run!r} under {history_root()}")
        return 1
    prev = resolve_run(args.prev) if args.prev else None
    rows = compare(run, prev)
    if args.json:
        print(json.dumps(rows, indent=1))
    else:
        _print_compare(run, rows)
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(_REPO))  # run as a script: make ``middleware`` importable
    raise SystemExit(main())
