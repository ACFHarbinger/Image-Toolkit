"""Shard planners: how each workload splits into retryable units (#826).

extraction → file slices · ComfyUI → prompt slices with fixed seeds ·
indexing → image-ID ranges · LoRA → one shard.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Dict, List, Mapping, Sequence, Tuple

from .spec import InputBlob, ShardSpec


def _chunks(items: Sequence[Any], size: int) -> List[Sequence[Any]]:
    if size < 1:
        raise ValueError("shard size must be >= 1")
    return [items[i:i + size] for i in range(0, len(items), size)]


def blob_for_file(path: str, chunk: int = 1 << 20) -> InputBlob:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            h.update(block)
    return InputBlob(h.hexdigest(), os.path.getsize(path), os.path.basename(path), path)


def plan_extraction(
    blobs: Sequence[InputBlob], per_shard: int, config: Mapping[str, Any]
) -> Tuple[Tuple[ShardSpec, ...], Dict[str, InputBlob]]:
    """One shard per ``per_shard`` source files; each shard carries the extraction config."""
    inputs = {b.sha256: b for b in blobs}  # identical files collapse to one upload
    keys = list(dict.fromkeys(b.sha256 for b in blobs))
    shards = tuple(
        ShardSpec(i, {"config": dict(config)}, tuple(group))
        for i, group in enumerate(_chunks(keys, per_shard))
    )
    return shards, inputs


def plan_comfy_batch(
    prompts: Sequence[str], per_shard: int, base_seed: int
) -> Tuple[ShardSpec, ...]:
    """Seeds are fixed per prompt, so a retried shard reproduces the same images."""
    items = [(i, p, base_seed + i) for i, p in enumerate(prompts)]
    return tuple(
        ShardSpec(n, {"items": [{"prompt_index": i, "prompt": p, "seed": s} for i, p, s in group]})
        for n, group in enumerate(_chunks(items, per_shard))
    )


def plan_index(image_ids: Sequence[int], per_shard: int) -> Tuple[ShardSpec, ...]:
    ordered = sorted(set(image_ids))
    return tuple(
        ShardSpec(n, {"id_min": group[0], "id_max": group[-1], "count": len(group)})
        for n, group in enumerate(_chunks(ordered, per_shard))
    )


def plan_lora(config: Mapping[str, Any], dataset: Sequence[InputBlob]) -> Tuple[Tuple[ShardSpec, ...], Dict[str, InputBlob]]:
    inputs = {b.sha256: b for b in dataset}
    return (ShardSpec(0, {"config": dict(config)}, tuple(inputs)),), inputs
