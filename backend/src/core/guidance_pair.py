"""Provenance-bound parent/variant comparison pair (#754 hold).

A successful Diff & Apply re-queue must not attach a verdict to whatever
images happen to be pinned. This module identifies the exact parent and
variant runs, materializes their first image outputs, and refuses a pair
whose identity or files no longer match.
"""
from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


class PairLoadError(ValueError):
    """Parent/variant outputs are missing, mismatched, or gone."""


@dataclass(frozen=True)
class PairRef:
    parent_prompt_id: str
    variant_prompt_id: str


@dataclass(frozen=True)
class OutputSpec:
    prompt_id: str
    local_path: str | None
    filename: str = ""
    subfolder: str = ""
    kind: str = "output"


@dataclass(frozen=True)
class BoundPair:
    parent_prompt_id: str
    variant_prompt_id: str
    parent_path: str
    variant_path: str
    generation: int

    @property
    def paths(self) -> list[str]:
        return [self.parent_path, self.variant_path]


def pair_ids_from_trajectory(traj: Any, variant_prompt_id: str | None = None) -> PairRef | None:
    """Parent/variant ids from the selected (or latest) trajectory step."""
    if traj is None:
        return None
    steps = getattr(traj, "steps", ()) or ()
    selected = None
    if isinstance(variant_prompt_id, str) and variant_prompt_id:
        selected = next(
            (step for step in steps if getattr(step, "variant_prompt_id", None) == variant_prompt_id),
            None,
        )
    step = selected or getattr(traj, "latest", None)
    if step is None:
        return None
    parent = str(getattr(step, "parent_prompt_id", "") or "")
    variant = getattr(step, "variant_prompt_id", None)
    if not parent or not isinstance(variant, str) or not variant:
        return None
    return PairRef(parent, variant)


def identity_error(
    parent_record: Any,
    variant_record: Any,
    *,
    expected_parent: str,
    expected_variant: str,
) -> str | None:
    """None when the records are exactly the requested parent→variant pair."""
    if parent_record is None or variant_record is None:
        return "missing run record"
    parent_id = getattr(parent_record, "prompt_id", None)
    variant_id = getattr(variant_record, "prompt_id", None)
    if parent_id != expected_parent or variant_id != expected_variant:
        return "run identity mismatch"
    linked = getattr(variant_record, "parent_prompt_id", None)
    if linked != expected_parent:
        return "variant parent mismatch"
    return None


def first_image_spec(record: Any) -> OutputSpec | None:
    """First local path or image OutputRef on *record*."""
    if record is None:
        return None
    prompt_id = str(getattr(record, "prompt_id", "") or "")
    local = getattr(record, "local_output_path", None)
    if isinstance(local, str) and local.strip():
        return OutputSpec(prompt_id, local.strip())
    for item in getattr(record, "outputs", ()) or ():
        filename = getattr(item, "filename", None)
        if not isinstance(filename, str) or not filename:
            continue
        kind_name = getattr(item, "kind", "")
        suffix = Path(filename).suffix.lower()
        if suffix and suffix not in _IMAGE_SUFFIXES and kind_name not in ("images", "gifs"):
            continue
        subfolder = getattr(item, "subfolder", "") or ""
        out_type = getattr(item, "type", None) or "output"
        return OutputSpec(
            prompt_id,
            None,
            filename=filename,
            subfolder=subfolder if isinstance(subfolder, str) else "",
            kind=out_type if isinstance(out_type, str) else "output",
        )
    return None


def _safe_part(part: str) -> str:
    cleaned = _SAFE.sub("_", part)
    if cleaned in {"", ".", ".."}:
        return "file"
    return cleaned


def contained_path(directory: Path, *parts: str) -> Path | None:
    """Resolve *parts* under *directory*; None if they would escape."""
    safe = tuple(_safe_part(part) for part in parts if part)
    if not safe:
        return None
    root = directory.resolve()
    target = (root.joinpath(*safe)).resolve()
    if target != root and root not in target.parents:
        return None
    return target


def materialize_output(
    spec: OutputSpec,
    *,
    cache_dir: Path,
    fetch: Callable[[str, str, str], bytes] | None = None,
    exists: Callable[[str], bool] = os.path.isfile,
) -> str | None:
    """Use an existing local file, or fetch bytes into a contained cache path."""
    if spec.local_path:
        path = os.path.expanduser(spec.local_path)
        return path if exists(path) else None
    if fetch is None or not spec.filename:
        return None
    target = contained_path(cache_dir, spec.prompt_id, spec.filename)
    if target is None:
        return None
    if exists(str(target)):
        return str(target)
    data = fetch(spec.filename, spec.subfolder, spec.kind)
    if not isinstance(data, (bytes, bytearray)) or not data:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes(bytes(data))
    tmp.replace(target)
    return str(target)


def load_comparison_pair(
    *,
    parent_record: Any,
    variant_record: Any,
    expected_parent: str,
    expected_variant: str,
    cache_dir: str | Path,
    fetch: Callable[[str, str, str], bytes] | None = None,
    exists: Callable[[str], bool] = os.path.isfile,
    generation: int,
) -> BoundPair:
    """Resolve both outputs or raise :class:`PairLoadError`."""
    mismatch = identity_error(
        parent_record,
        variant_record,
        expected_parent=expected_parent,
        expected_variant=expected_variant,
    )
    if mismatch:
        raise PairLoadError(mismatch)
    parent_spec = first_image_spec(parent_record)
    variant_spec = first_image_spec(variant_record)
    if parent_spec is None or variant_spec is None:
        raise PairLoadError("outputs unavailable")
    root = Path(cache_dir)
    parent_path = materialize_output(parent_spec, cache_dir=root, fetch=fetch, exists=exists)
    variant_path = materialize_output(variant_spec, cache_dir=root, fetch=fetch, exists=exists)
    if not parent_path or not variant_path:
        raise PairLoadError("outputs unavailable")
    if not exists(parent_path) or not exists(variant_path):
        raise PairLoadError("outputs deleted")
    return BoundPair(
        parent_prompt_id=expected_parent,
        variant_prompt_id=expected_variant,
        parent_path=parent_path,
        variant_path=variant_path,
        generation=generation,
    )


def pair_matches_trajectory(
    bound: BoundPair,
    traj: Any,
    variant_prompt_id: str | None = None,
) -> bool:
    refs = pair_ids_from_trajectory(traj, variant_prompt_id)
    return (
        refs is not None
        and refs.parent_prompt_id == bound.parent_prompt_id
        and refs.variant_prompt_id == bound.variant_prompt_id
    )


def pair_files_alive(bound: BoundPair, exists: Callable[[str], bool] = os.path.isfile) -> bool:
    return exists(bound.parent_path) and exists(bound.variant_path)


def persist_verdict(
    manager: Any,
    traj: Any,
    variant_prompt_id: str | None,
    persist_sidecar: Callable[[Any], None] | None = None,
) -> None:
    """Write the evaluated trajectory onto the variant record and sidecar."""
    if traj is None:
        return
    payload = {"guidance_trajectory": traj.to_dict()}
    updater = getattr(manager, "update_run_meta", None)
    if callable(updater) and variant_prompt_id:
        updater(variant_prompt_id, payload)
    if callable(persist_sidecar):
        persist_sidecar(traj)
