"""#743: file-based adapter geometry — effective rank, ΔW, principal direction.

Synthetic safetensors only: no base model, no GPU. The 0.99-energy
definition matches training_hooks.lora_effective_rank.
"""
from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file

from middleware.src.core.adapter_reports import RankHistoryReport
from middleware.src.models.hooks.adapter_geometry import (
    checkpoint_rank_snapshot,
    load_adapter_deltas,
    principal_direction,
    rank_history,
)


def _peft_file(path: Path, modules: dict[str, tuple[torch.Tensor, torch.Tensor]]) -> Path:
    """Write a peft-style adapter file: ...<module>.lora_A/lora_B.weight."""
    state = {}
    for module, (a, b) in modules.items():
        state[f"base_model.model.{module}.lora_A.weight"] = a.contiguous()
        state[f"base_model.model.{module}.lora_B.weight"] = b.contiguous()
    save_file(state, str(path))
    return path


def _kohya_file(path: Path, modules: dict[str, tuple[torch.Tensor, torch.Tensor]]) -> Path:
    state = {}
    for module, (a, b) in modules.items():
        state[f"{module}.lora_down.weight"] = a.contiguous()
        state[f"{module}.lora_up.weight"] = b.contiguous()
    save_file(state, str(path))
    return path


def _factors(rank: int, scales: torch.Tensor, out: int = 6, seed: int = 0) -> tuple[torch.Tensor, torch.Tensor]:
    """A with per-row scales s_i · e_i; B orthogonal columns → ΔW = B @ A
    has singular values proportional to `scales`."""
    generator = torch.Generator().manual_seed(seed)
    a = torch.zeros(rank, 2 * rank)
    for i in range(rank):
        a[i, i] = float(scales[i])
    b = torch.randn(out, rank, generator=generator)
    b, _ = torch.linalg.qr(b)  # orthonormal columns: singular values = scales
    return a, b


def test_peft_format_parsed_and_prefix_stripped(tmp_path):
    a, b = _factors(4, torch.tensor([1.0, 1.0, 1.0, 0.01]))
    path = _peft_file(tmp_path / "adapter_model.safetensors", {"unet.proj_out": (a, b)})
    deltas = load_adapter_deltas(path)
    assert list(deltas) == ["unet.proj_out"]
    assert torch.equal(deltas["unet.proj_out"][0], a)


def test_kohya_format_parsed(tmp_path):
    a, b = _factors(4, torch.tensor([1.0, 1.0, 1.0, 0.01]))
    path = _kohya_file(tmp_path / "lycoris_net.safetensors", {"unet.proj_out": (a, b)})
    deltas = load_adapter_deltas(path)
    assert list(deltas) == ["unet.proj_out"]
    assert torch.equal(deltas["unet.proj_out"][1], b)


def test_effective_rank_matches_energy_threshold(tmp_path):
    # 3 strong directions + one negligible → eff_rank 3 of chosen 4.
    a, b = _factors(4, torch.tensor([1.0, 1.0, 1.0, 0.01]))
    path = _peft_file(tmp_path / "adapter_model.safetensors", {"unet.q": (a, b)})
    snapshot = checkpoint_rank_snapshot("final", path)
    (row,) = snapshot.rows
    assert row.rank == 4
    assert row.effective == 3
    assert row.fro == pytest.approx(float(torch.tensor([1.0, 1.0, 1.0, 0.01]).norm()), rel=1e-4)
    utilization = snapshot.utilization()
    assert utilization is not None
    assert utilization.chosen == 4
    assert utilization.effective == 3


def test_full_rank_module_counts_as_pinned(tmp_path):
    a, b = _factors(4, torch.tensor([1.0, 1.0, 1.0, 1.0]))
    path = _peft_file(tmp_path / "adapter_model.safetensors", {"unet.k": (a, b)})
    snapshot = checkpoint_rank_snapshot("final", path)
    assert snapshot.pinned_fraction == 1.0
    assert snapshot.utilization().effective == 4


def test_rank_history_walks_epochs_and_final_in_order(tmp_path):
    output = tmp_path / "out"
    for epoch, scale in ((1, 1.0), (2, 0.01)):
        directory = output / f"checkpoint-epoch{epoch:04d}"
        directory.mkdir(parents=True)
        a, b = _factors(2, torch.tensor([scale, scale]))
        _peft_file(directory / "adapter_model.safetensors", {"unet.v": (a, b)})
    a, b = _factors(2, torch.tensor([1.0, 1.0]))
    _peft_file(output / "lora_weights.safetensors", {"unet.v": (a, b)})

    report = rank_history(output)
    assert isinstance(report, RankHistoryReport)
    assert [s.label for s in report.snapshots] == ["epoch 0001", "epoch 0002", "final"]
    assert report.latest().label == "final"
    assert report.latest().utilization() is not None


def test_rank_history_skips_artifactless_checkpoints(tmp_path):
    output = tmp_path / "out"
    (output / "checkpoint-epoch0001").mkdir(parents=True)  # no adapter file
    report = rank_history(output)
    assert report.snapshots == ()
    assert report.note


def test_rank_history_missing_dir(tmp_path):
    report = rank_history(tmp_path / "does-not-exist")
    assert report.snapshots == ()
    assert "not found" in report.note


def test_principal_direction_picks_max_delta_module(tmp_path):
    big = _factors(2, torch.tensor([5.0, 0.1]))
    small = _factors(2, torch.tensor([0.1, 0.1]))
    path = _peft_file(
        tmp_path / "adapter_model.safetensors",
        {"unet.big": big, "unet.small": small},
    )
    spec, u1, v1 = principal_direction(path)
    assert spec.module == "unet.big"
    assert spec.chosen_rank == 2
    assert spec.sigma == pytest.approx(5.0, rel=1e-3)
    assert 0.0 < spec.energy_fraction <= 1.0
    # Unit vectors, and perturbation math reproduces ΔW's leading term.
    assert torch.allclose(u1.norm(), torch.tensor(1.0), atol=1e-5)
    assert torch.allclose(v1.norm(), torch.tensor(1.0), atol=1e-5)
    # The leading rank-1 term of ΔW — compare against ΔW's own top SVD
    # component, not the full (rank-2) ΔW.
    a, b = big
    delta_w = b @ a
    u, sv, vh = torch.linalg.svd(delta_w, full_matrices=False)
    leading = sv[0] * u[:, 0].outer(vh[0, :])
    assert torch.allclose(spec.sigma * u1.outer(v1), leading, atol=1e-4)


def test_principal_direction_explicit_module(tmp_path):
    big = _factors(2, torch.tensor([5.0, 0.1]))
    small = _factors(2, torch.tensor([0.1, 0.1]))
    path = _peft_file(
        tmp_path / "adapter_model.safetensors",
        {"unet.big": big, "unet.small": small},
    )
    spec, _u, _v = principal_direction(path, module="unet.small")
    assert spec.module == "unet.small"
    with pytest.raises(ValueError, match="not present"):
        principal_direction(path, module="unet.absent")


def test_zero_adapter_has_zero_effective_rank(tmp_path):
    from safetensors.torch import save_file

    from middleware.src.models.hooks.adapter_geometry import checkpoint_rank_snapshot
    path = tmp_path / "adapter_model.safetensors"
    save_file({"layer.lora_A.weight": torch.ones(2, 4),
               "layer.lora_B.weight": torch.zeros(3, 2)}, str(path))
    report = checkpoint_rank_snapshot("zero", path)
    assert report.rows[0].effective == 0
