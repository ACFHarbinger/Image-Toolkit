"""
SVD effective-rank analysis for a trained LoRA checkpoint.

Usage:
    python scripts/lora_analyze.py outputs/my_char/checkpoint-epoch0010
    python scripts/lora_analyze.py outputs/my_char/lora_weights.safetensors
"""

import sys
from collections import defaultdict
from pathlib import Path

import torch
import safetensors.torch as sf


def analyze(checkpoint_path: str) -> None:
    p = Path(checkpoint_path)

    # Accept either a directory or a direct .safetensors file
    if p.is_dir():
        candidates = sorted(p.rglob("lora_weights.safetensors")) + sorted(p.rglob("*.safetensors"))
        if not candidates:
            print(f"No .safetensors files found in {p}")
            sys.exit(1)
        path = candidates[0]
    else:
        path = p

    print(f"Loading {path}\n")
    state = sf.load_file(str(path))

    # Group lora_A / lora_B tensors by layer name
    layers: dict[str, dict] = defaultdict(dict)
    for k, v in state.items():
        if "lora_A" in k:
            layers[k.replace(".lora_A.weight", "")]["A"] = v
        elif "lora_B" in k:
            layers[k.replace(".lora_B.weight", "")]["B"] = v

    if not layers:
        print("No lora_A/lora_B tensors found — is this a LoRA checkpoint?")
        sys.exit(1)

    rows = []
    for name, d in layers.items():
        if "A" not in d or "B" not in d:
            continue
        W = d["B"].float() @ d["A"].float()
        s = torch.linalg.svdvals(W)
        rank = d["A"].shape[0]
        cumvar = (s ** 2).cumsum(0) / (s ** 2).sum().clamp(min=1e-12)
        eff = int((cumvar < 0.99).sum()) + 1
        fro = float(W.norm())
        rows.append((name, eff, rank, fro))

    rows.sort(key=lambda r: -r[3])

    print(f"{'Layer':<50} {'eff_rank':>8} {'rank':>6} {'‖ΔW‖_F':>10}  note")
    print("-" * 84)
    for name, eff, rank, fro in rows[:40]:
        short = name.split(".")[-2] if "." in name else name
        if eff <= rank // 4:
            note = "← underfit (reduce rank or increase steps)"
        elif eff >= rank:
            note = "← saturated (raise rank / add rsLoRA)"
        else:
            note = ""
        print(f"{short:<50} {eff:>8} {rank:>6} {fro:>10.4f}  {note}")

    avg_util = sum(r[1] / r[2] for r in rows) / len(rows) * 100 if rows else 0
    print(f"\nAverage rank utilisation: {avg_util:.1f}%")
    if avg_util < 30:
        print("Tip: rank is too high for this dataset — try rank=8 or rank=16.")
    elif avg_util > 85:
        print("Tip: rank is nearly saturated — try rank=32 or enable rsLoRA.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/lora_analyze.py <checkpoint_dir_or_file>")
        sys.exit(1)
    analyze(sys.argv[1])
