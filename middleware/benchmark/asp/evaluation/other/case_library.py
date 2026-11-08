"""User-named ASP case subsets and extra case directories.

Canonical slices stay fixed. This store (``ASP_EVAL_LIBRARY`` when set,
otherwise the shared evaluator path outside the repo) holds subsets a person
keeps between sessions, plus directories whose cases are not named
``asp_test*``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from middleware.benchmark.asp.slices import DevelopmentSlice, list_slices

_OUTPUT_SUFFIX = "_anime_stitch.png"
_DIR_MARKERS = ("panorama.png", "baseline.png", "stitch.png")


def store_path() -> Path:
    """Library file: ``ASP_EVAL_LIBRARY`` when set, otherwise the shared evaluator path."""
    override = os.environ.get("ASP_EVAL_LIBRARY")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Downloads" / "Data" / "Tests" / "asp-benchmark" / "evaluator" / "library.json"


def load_store() -> dict:
    """Return the library. A missing file is an empty store and is not created."""
    path = store_path()
    if not path.is_file():
        return {"subsets": [], "directories": []}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {"subsets": [], "directories": []}
    subsets = data.get("subsets")
    directories = data.get("directories")
    return {
        "subsets": [item for item in subsets if isinstance(item, dict)] if isinstance(subsets, list) else [],
        "directories": (
            [item for item in directories if isinstance(item, dict)] if isinstance(directories, list) else []
        ),
    }


def _write_store(store: dict) -> None:
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "subsets": store.get("subsets", []),
        "directories": store.get("directories", []),
    }
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _unique_tokens(values: list[str] | None, *, lower: bool) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for value in values or []:
        text = str(value).strip()
        if lower:
            text = text.lower()
        if not text or text in seen:
            continue
        seen.add(text)
        cleaned.append(text)
    return cleaned


def list_user_subsets() -> list[dict]:
    """Stored subsets: name, description, tags, case_ids."""
    rows: list[dict] = []
    for raw in load_store()["subsets"]:
        name = str(raw.get("name", "")).strip()
        if not name:
            continue
        tags = raw.get("tags")
        case_ids = raw.get("case_ids")
        description = raw.get("description", "")
        rows.append(
            {
                "name": name,
                "description": "" if description is None else str(description),
                "tags": [str(tag) for tag in tags] if isinstance(tags, list) else [],
                "case_ids": [str(case_id) for case_id in case_ids] if isinstance(case_ids, list) else [],
            }
        )
    return rows


def upsert_subset(
    name: str,
    case_ids: list[str],
    *,
    description: str = "",
    tags: list[str] | None = None,
) -> dict:
    """Insert or replace a subset. Name match is case-sensitive after stripping."""
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("subset name must not be empty")
    record = {
        "name": cleaned_name,
        "description": "" if description is None else str(description),
        "tags": _unique_tokens(tags, lower=True),
        "case_ids": _unique_tokens(case_ids, lower=False),
    }
    store = load_store()
    subsets = store["subsets"]
    for index, existing in enumerate(subsets):
        if str(existing.get("name", "")).strip() == cleaned_name:
            subsets[index] = record
            break
    else:
        subsets.append(record)
    _write_store(store)
    return {
        "name": record["name"],
        "description": record["description"],
        "tags": list(record["tags"]),
        "case_ids": list(record["case_ids"]),
    }


def delete_subset(name: str) -> bool:
    """Remove a subset by stripped, case-sensitive name. False when absent."""
    key = name.strip()
    if not key:
        return False
    store = load_store()
    kept: list[dict] = []
    removed = False
    for existing in store["subsets"]:
        if str(existing.get("name", "")).strip() == key:
            removed = True
            continue
        kept.append(existing)
    if not removed:
        return False
    store["subsets"] = kept
    _write_store(store)
    return True


def list_directories() -> list[dict]:
    """Registered case directories: path, label."""
    rows: list[dict] = []
    for raw in load_store()["directories"]:
        path = str(raw.get("path", "")).strip()
        if not path:
            continue
        label = raw.get("label", "")
        rows.append({"path": path, "label": "" if label is None else str(label)})
    return rows


def add_directory(path: str, label: str = "") -> dict:
    """Register an absolute directory. The same path replaces the label."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(resolved)
    record = {"path": str(resolved), "label": "" if label is None else str(label)}
    store = load_store()
    directories = store["directories"]
    for index, existing in enumerate(directories):
        if str(existing.get("path", "")) == record["path"]:
            directories[index] = record
            break
    else:
        directories.append(record)
    _write_store(store)
    return {"path": record["path"], "label": record["label"]}


def remove_directory(path: str) -> bool:
    """Remove a directory registered under the same resolved path."""
    target = str(Path(path).expanduser().resolve())
    store = load_store()
    kept: list[dict] = []
    removed = False
    for existing in store["directories"]:
        if str(existing.get("path", "")) == target:
            removed = True
            continue
        kept.append(existing)
    if not removed:
        return False
    store["directories"] = kept
    _write_store(store)
    return True


def _remember(names: set[str], name: str) -> None:
    if name:
        names.add(name)


def cases_in_directory(path: str) -> list[str]:
    """Sorted case names from stitch outputs, case subdirectories, and flat pngs."""
    root = Path(path).expanduser()
    names: set[str] = set()
    for image in (root / "output").glob(f"*{_OUTPUT_SUFFIX}"):
        if image.is_file():
            _remember(names, image.name[: -len(_OUTPUT_SUFFIX)])
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir() and any((child / marker).is_file() for marker in _DIR_MARKERS):
                _remember(names, child.name)
        for image in root.glob("*.png"):
            if image.is_file() and not image.stem.startswith("."):
                _remember(names, image.stem)
    return sorted(names)


def resolve_case_file(path: str, name: str) -> str | None:
    """First existing case image: stitch output, then subdir markers, then a flat png."""
    root = Path(path).expanduser()
    case = name.strip()
    if not case:
        return None
    candidates = (
        root / "output" / f"{case}{_OUTPUT_SUFFIX}",
        root / case / "panorama.png",
        root / case / "baseline.png",
        root / case / "stitch.png",
        root / f"{case}.png",
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return None


def _matching_subset(name: str) -> dict | None:
    query = name.strip()
    if not query:
        return None
    folded = query.lower()
    fallback: dict | None = None
    for subset in list_user_subsets():
        stored = subset["name"]
        if stored == query:
            return subset
        if fallback is None and stored.lower() == folded:
            fallback = subset
    return fallback


def user_slice(name: str) -> DevelopmentSlice | None:
    """User subset as a development slice, or None. Does not raise when missing."""
    subset = _matching_subset(name)
    if subset is None:
        return None
    return DevelopmentSlice(
        name=subset["name"],
        version="user",
        description=subset["description"],
        case_ids=tuple(subset["case_ids"]),
        metadata={"tags": list(subset["tags"])},
    )


def selectable_subsets() -> list[dict]:
    """Built-in slices first (kind ``builtin``), then user subsets (kind ``user``)."""
    builtin = [
        {
            "kind": "builtin",
            "name": slc.name,
            "description": slc.description,
            "case_ids": list(slc.case_ids),
        }
        for slc in list_slices()
    ]
    user = [
        {
            "kind": "user",
            "name": subset["name"],
            "description": subset["description"],
            "tags": list(subset["tags"]),
            "case_ids": list(subset["case_ids"]),
        }
        for subset in list_user_subsets()
    ]
    return builtin + user
