"""File-based adapter geometry (#743): effective rank + ΔW from checkpoints.

Same 0.99-energy singular-value definition as ``training_hooks.lora_effective_rank``,
computed from saved checkpoint safetensors instead of an in-memory peft
model — so the rank chart needs no base-model load and works post-hoc on
any run's output dir. Supports the two on-disk formats this repo writes:

* peft ``save_pretrained`` / ``get_peft_model_state_dict`` —
  ``...lora_A.weight`` / ``...lora_B.weight`` (V2 checkpoints + V1 finals)
* kohya/LyCORIS ``save_weights`` — ``...lora_down.weight`` /
  ``...lora_up.weight`` (LyCORIS finals)

Effective rank is invariant to alpha scaling (ratios of singular values),
so no adapter config is needed.
"""
from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path

import torch
from safetensors.torch import load_file

from middleware.src.core.adapter_reports import (
    RANK_ENERGY_THRESHOLD,
    CheckpointRankSnapshot,
    DirectionSpec,
    ModuleRankRow,
    RankHistoryReport,
)

log = logging.getLogger(__name__)

_ADAPTER_FILENAMES = ("adapter_model.safetensors", "lora_weights.safetensors", "lycoris_net.safetensors")
_CHECKPOINT_DIR_RE = re.compile(r"checkpoint-epoch(\d+)$")
_KEY_STRIP_PREFIXES = ("base_model.model.", "base_model.")
_DOWN_KEYS = ("lora_A", "lora_down")
_UP_KEYS = ("lora_B", "lora_up")


def _normalize_key(key: str) -> str:
    for prefix in _KEY_STRIP_PREFIXES:
        if key.startswith(prefix):
            key = key[len(prefix):]
    return key


def _split_module(key: str) -> tuple[str, str] | None:
    """'...proj.lora_A.weight' -> ('...proj', 'lora_A')."""
    for down in _DOWN_KEYS + _UP_KEYS:
        marker = f".{down}.weight"
        if key.endswith(marker):
            return key[: -len(marker)], down
    return None


def load_adapter_deltas(path: str | Path) -> dict[str, tuple[torch.Tensor, torch.Tensor]]:
    """Module key -> (A, B) tensors (low-rank factors of ΔW = B @ A)."""
    state = load_file(str(path))
    config_path = Path(path).parent / "adapter_config.json"
    config = json.loads(config_path.read_text()) if config_path.is_file() else {}
    modules: dict[str, dict[str, torch.Tensor]] = {}
    for key, tensor in state.items():
        parts = _split_module(key)
        if parts is None or tensor.dim() not in (1, 2):
            continue
        module, factor = parts
        modules.setdefault(_normalize_key(module), {})[factor] = tensor.detach().float()
    out: dict[str, tuple[torch.Tensor, torch.Tensor]] = {}
    for module, factors in modules.items():
        a = factors.get("lora_A", factors.get("lora_down"))
        b = factors.get("lora_B", factors.get("lora_up"))
        if a is not None and b is not None and a.dim() == 2:
            rank = a.shape[0]
            alpha = config.get("lora_alpha", rank)
            for suffix, value in config.get("alpha_pattern", {}).items():
                if module == suffix or module.endswith("." + suffix):
                    alpha = value
            intrinsic_alpha = state.get(module + ".alpha")
            if intrinsic_alpha is not None:
                alpha = float(intrinsic_alpha)
            scale = float(alpha) / (math.sqrt(rank) if config.get("use_rslora") else rank)
            out[module] = (a, b * scale)
    return out


def _module_rows(deltas: dict[str, tuple[torch.Tensor, torch.Tensor]]) -> list[ModuleRankRow]:
    rows: list[ModuleRankRow] = []
    for module in sorted(deltas):
        a, b = deltas[module]
        try:
            _, rb = torch.linalg.qr(b, mode="reduced")
            _, ra = torch.linalg.qr(a.T, mode="reduced")
            sv = torch.linalg.svdvals(rb @ ra.T)
        except Exception as exc:  # pragma: no cover - malformed tensors
            log.debug("svdvals failed for %s: %s", module, exc)
            continue
        energy = sv.float() ** 2
        total = energy.sum().clamp(min=1e-12)
        cumvar = energy.cumsum(0) / total
        effective = 0 if float(energy.sum()) == 0 else int((cumvar < RANK_ENERGY_THRESHOLD).sum().item()) + 1
        rows.append(
            ModuleRankRow(
                module=module,
                effective=min(effective, int(a.shape[0])),
                rank=int(a.shape[0]),
                max_sv=float(sv.max()),
                fro=float(sv.norm()),
            )
        )
    return rows


def checkpoint_rank_snapshot(label: str, adapter_path: str | Path) -> CheckpointRankSnapshot:
    return CheckpointRankSnapshot(
        label=label,
        source=str(adapter_path),
        rows=tuple(_module_rows(load_adapter_deltas(adapter_path))),
    )


def _adapter_file(directory: Path) -> Path | None:
    for name in _ADAPTER_FILENAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def rank_history(output_dir: str | Path) -> RankHistoryReport:
    """Effective-rank snapshots for every saved checkpoint + the final
    artifact of a training output dir, oldest first."""
    output_dir = Path(output_dir)
    if not output_dir.is_dir():
        return RankHistoryReport(output_dir=str(output_dir), note="output dir not found")

    snapshots: list[CheckpointRankSnapshot] = []
    epochs: list[tuple[int, Path]] = []
    for child in output_dir.iterdir():
        match = _CHECKPOINT_DIR_RE.match(child.name)
        if match and child.is_dir():
            epochs.append((int(match.group(1)), child))
    for epoch, directory in sorted(epochs):
        adapter = _adapter_file(directory)
        if adapter is None:
            continue
        try:
            snapshots.append(checkpoint_rank_snapshot(f"epoch {epoch:04d}", adapter))
        except Exception as exc:  # unreadable/corrupt checkpoint: skip, keep walking
            log.debug("skipping checkpoint %s: %s", directory, exc)

    final = _adapter_file(output_dir)
    if final is not None:
        try:
            snapshots.append(checkpoint_rank_snapshot("final", final))
        except Exception as exc:
            log.debug("skipping final artifact %s: %s", final, exc)

    note = "" if snapshots else "no adapter artifacts found"
    return RankHistoryReport(output_dir=str(output_dir), snapshots=tuple(snapshots), note=note)


def principal_direction(
    adapter_path: str | Path,
    module: str | None = None,
) -> tuple[DirectionSpec, torch.Tensor, torch.Tensor]:
    """Leading singular pair of the max-‖ΔW‖ module (or a chosen module).

    Returns the direction spec plus u1 (output side) and v1 (input side)
    unit vectors; the #748 slice perturbs the module's output by
    α · σ1 · u1 · (v1ᵀ x) via a forward hook — no weight mutation.
    """
    deltas = load_adapter_deltas(adapter_path)
    if not deltas:
        raise ValueError(f"no LoRA/LyCORIS factors found in {adapter_path}")
    key = module or max(deltas, key=lambda k: float(torch.trace((deltas[k][1].T @ deltas[k][1]) @ (deltas[k][0] @ deltas[k][0].T))))
    if key not in deltas:
        raise ValueError(f"module {module!r} not present in {adapter_path}")
    a, b = deltas[key]
    qb, rb = torch.linalg.qr(b, mode="reduced")
    qa, ra = torch.linalg.qr(a.T, mode="reduced")
    uc, sv, vhc = torch.linalg.svd(rb @ ra.T, full_matrices=False)
    u, vh = qb @ uc, vhc @ qa.T
    sigma = float(sv[0])
    energy_fraction = float(sv[0] ** 2 / (sv.float() ** 2).sum().clamp(min=1e-12))
    spec = DirectionSpec(
        module=key,
        sigma=sigma,
        energy_fraction=energy_fraction,
        chosen_rank=int(a.shape[0]),
    )
    return spec, u[:, 0].contiguous(), vh[0, :].contiguous()
