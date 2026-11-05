"""Optional description, tags, and case deltas for archived ASP runs.

Nothing is written unless ``annotate_run`` or ``snapshot_outputs`` is called.
"""

from __future__ import annotations

import json
from pathlib import Path

from middleware.benchmark.asp import run_history


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _tag_key(tag: object) -> str:
    return str(tag).strip().lower()


def _normalize_tags(tags: list[str] | None) -> list[str]:
    """Strip, lowercase, drop empties, and de-duplicate while keeping order."""
    if not tags:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for tag in tags:
        key = _tag_key(tag)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _run_dict(info: run_history.RunInfo) -> dict:
    meta = info.meta
    raw_cases = meta.get("cases")
    cases = [str(case) for case in raw_cases] if isinstance(raw_cases, list) else info.cases()
    raw_tags = meta.get("tags")
    tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
    description = meta.get("description")
    return {
        "run_id": info.run_id,
        "label": _text(meta.get("label")),
        "description": description if isinstance(description, str) else "",
        "tags": tags,
        "created": _text(meta.get("created")),
        "status": _text(meta.get("status")),
        "cases": cases,
        "path": str(info.path),
    }


def _write_json(path: Path, value: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def _require_run(run_id: str, root: Path | None) -> run_history.RunInfo:
    """Exact run id only. Prefix and label matches would annotate the wrong run."""
    info = run_history.resolve_run(run_id, root)
    if info is None or info.run_id != run_id:
        raise FileNotFoundError(run_id)
    return info


def _delta_asp(current: object, previous: object) -> float | None:
    if isinstance(current, bool) or isinstance(previous, bool):
        return None
    if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
        return float(current) - float(previous)
    return None


def list_runs(root: Path | None = None) -> list[dict]:
    """Oldest first. Each dict has run_id, label (str), description (str),
    tags (list[str]), created (str), status (str), cases (list[str]), path (str).
    Missing description/tags become "" and []."""
    return [_run_dict(info) for info in run_history.list_runs(root)]


def annotate_run(
    run_id: str,
    *,
    description: str = "",
    tags: list[str] | None = None,
    root: Path | None = None,
) -> dict:
    """Write description and tags onto that run's run.json. Tags are stripped,
    lowercased, de-duplicated, empties dropped, order preserved.
    Raise FileNotFoundError if the run id is unknown.
    Return the same dict shape as list_runs."""
    info = _require_run(run_id, root)
    meta_path = info.path / "run.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["description"] = description
    meta["tags"] = _normalize_tags(tags)
    _write_json(meta_path, meta)
    return _run_dict(run_history.RunInfo(info.run_id, info.path, meta))


def filter_by_tags(runs: list[dict], tags: list[str]) -> list[dict]:
    """If tags is empty, return runs unchanged. Otherwise keep runs that contain
    every requested tag (AND). Tag match is case-insensitive."""
    if not tags:
        return runs
    needed = [_tag_key(tag) for tag in tags]
    kept: list[dict] = []
    for run in runs:
        raw = run.get("tags")
        have = {_tag_key(tag) for tag in raw} if isinstance(raw, list) else set()
        if all(tag in have for tag in needed):
            kept.append(run)
    return kept


def compare_cases(
    run_id: str,
    prev_id: str | None = None,
    *,
    cases: list[str] | None = None,
    root: Path | None = None,
) -> list[dict]:
    """Use run_history.compare. If cases is not None, keep only those case names
    that the compare result includes, in the order given in cases.
    Add delta_asp: float | None = asp - prev_asp when both values are numbers,
    else None. Do not drop the keys run_history.compare already returns.
    Raise FileNotFoundError if run_id is unknown."""
    run = _require_run(run_id, root)
    prev = _require_run(prev_id, root) if prev_id is not None else None
    rows = run_history.compare(run, prev, root)
    if cases is not None:
        by_case = {row["case"]: row for row in rows}
        rows = [by_case[name] for name in cases if name in by_case]
    for row in rows:
        # compare names the previous score asp_prev, not prev_asp.
        row["delta_asp"] = _delta_asp(row.get("asp"), row.get("asp_prev"))
    return rows


def snapshot_outputs(
    base_dir: str,
    cases: list[str],
    *,
    description: str,
    tags: list[str],
    label: str | None = None,
    root: Path | None = None,
) -> dict:
    """User opted in. Create a run with run_history.new_run(cases, label=label, root=root).
    For each case name, if {base_dir}/output/{case}_anime_stitch.png exists, call
    run_history.archive_case with a row dict:
      {"name": case, "anime_path": that png path}
    Then run_history.finish_run(run_dir, status="saved").
    Then annotate_run with description and tags.
    Return the annotated dict.
    If no case file exists, still create the run, finish it, and annotate it."""
    run_dir = run_history.new_run(list(cases), label=label, root=root)
    output = Path(base_dir) / "output"
    for case in cases:
        png = output / f"{case}_anime_stitch.png"
        if png.is_file():
            run_history.archive_case(run_dir, {"name": case, "anime_path": str(png)})
    run_history.finish_run(run_dir, status="saved")
    return annotate_run(run_dir.name, description=description, tags=tags, root=root)
