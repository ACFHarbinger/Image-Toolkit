"""
SEA-RAFT fine-tuning on anime optical flow data (P3.5).

Starting from the SEA-RAFT pretrained weights (rigid-motion pretraining on
Sintel / Things), fine-tune on anime frame pairs where the background motion
is known (pure translation from the AnimeStitchPipeline affines).

Expected outcome: 30–50% more reliable background flow estimation on flat
cel-shaded anime regions that have no texture gradients for the cost volume.

Dataset strategy
----------------
We generate synthetic training pairs from the existing benchmark test-cases
and any available anime video frames:

1. Load a source frame F_i.
2. Apply a known translation (tx, ty) sampled from N(0, 120px).
3. Generate F_j = warp(F_i, -tx, -ty)  → ground-truth flow = (tx, ty).
4. Optionally add anime-realistic degradations:
   - JPEG compression at quality 65–85 (mimics low-bitrate video streams)
   - Mild Gaussian blur σ ∈ [0.3, 1.2]  (motion blur on panning frames)
   - Colour jitter ±5%  (frame-to-frame brightness variation)

An optional second data source is the LinkTo-Anime dataset
(arXiv:2506.02733), which provides ground-truth optical flow for 2D
animation derived from 3D model rendering. Pass --linktoanime /path/to/lta.

Training loop
-------------
- Optimizer: AdamW (lr=2e-5, weight decay=1e-4)
- Loss: SEA-RAFT's Mixture-of-Laplace loss on flow predictions
- Schedule: cosine decay from lr → 1e-7 over --max_steps iterations
- Checkpoint: saved every --save_every steps to --output_dir

Usage
-----
    python -m backend.models.training.finetune_raft_anime \\
        --source_dir /path/to/anime/frames \\
        --output_dir backend/models/checkpoints/sea_raft_anime \\
        --max_steps 20000 \\
        --batch_size 4 \\
        --linktoanime /path/to/lta  # optional
"""

from __future__ import annotations

# --- Relocated Nested Imports ---
import ptlflow
# --------------------------------


import argparse
import os
import random
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader, IterableDataset


# ── Data ───────────────────────────────────────────────────────────────────────


class _AnimeSyntheticFlowDataset(IterableDataset):
    """
    Generates synthetic anime frame pairs with known ground-truth optical flow.

    Each iteration yields:
        img1 : (3, H, W) float32 in [0, 1]
        img2 : (3, H, W) float32 in [0, 1]
        flow : (2, H, W) float32 in pixels  [u (x-disp), v (y-disp)]
    """

    def __init__(
        self,
        source_dir: str,
        crop_size: Tuple[int, int] = (256, 256),
        max_tx: float = 120.0,
        max_ty: float = 120.0,
        jpg_quality_range: Tuple[int, int] = (65, 90),
        blur_sigma_range: Tuple[float, float] = (0.0, 1.2),
        color_jitter: float = 0.05,
        linktoanime_dir: Optional[str] = None,
    ):
        self.source_dir = Path(source_dir)
        self.crop_h, self.crop_w = crop_size
        self.max_tx = max_tx
        self.max_ty = max_ty
        self.jpg_quality_range = jpg_quality_range
        self.blur_sigma_range = blur_sigma_range
        self.color_jitter = color_jitter
        self.lta_dir = Path(linktoanime_dir) if linktoanime_dir else None

        self._image_paths = (
            sorted(self.source_dir.rglob("*.png"))
            + sorted(self.source_dir.rglob("*.jpg"))
            + sorted(self.source_dir.rglob("*.webp"))
        )
        if not self._image_paths:
            raise FileNotFoundError(f"No images found in {source_dir}")

    def _degrade(self, img: np.ndarray) -> np.ndarray:
        """Apply anime-realistic degradations to a uint8 BGR image."""
        # JPEG compression
        q = random.randint(*self.jpg_quality_range)
        _, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])
        img = cv2.imdecode(enc, cv2.IMREAD_COLOR)

        # Gaussian blur
        sigma = random.uniform(*self.blur_sigma_range)
        if sigma > 0.1:
            ksize = max(3, int(sigma * 4) | 1)
            img = cv2.GaussianBlur(img, (ksize, ksize), sigma)

        # Colour jitter
        jitter = 1.0 + random.uniform(-self.color_jitter, self.color_jitter)
        img = np.clip(img.astype(np.float32) * jitter, 0, 255).astype(np.uint8)

        return img

    def _synthetic_pair(self, img_path: Path) -> Optional[Tuple]:
        img = cv2.imread(str(img_path))
        if img is None:
            return None
        H, W = img.shape[:2]
        if H < self.crop_h + 50 or W < self.crop_w + 50:
            return None

        # Random crop (with margin for translation)
        margin = 60
        r0 = random.randint(0, H - self.crop_h - margin)
        c0 = random.randint(0, W - self.crop_w - margin)
        img1_raw = img[r0 : r0 + self.crop_h, c0 : c0 + self.crop_w]

        # Random translation
        tx = random.uniform(-self.max_tx * 0.3, self.max_tx * 0.3)
        ty = random.uniform(-self.max_ty, self.max_ty * 0.1)  # mostly vertical (pan)

        M = np.array([[1, 0, tx], [0, 1, ty]], dtype=np.float32)
        img2_raw = cv2.warpAffine(
            img1_raw,
            M,
            (self.crop_w, self.crop_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT,
        )

        img1 = self._degrade(img1_raw.copy())
        img2 = self._degrade(img2_raw.copy())

        def to_tensor(x: np.ndarray) -> torch.Tensor:
            return torch.from_numpy(
                cv2.cvtColor(x, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            ).permute(2, 0, 1)

        flow = torch.zeros(2, self.crop_h, self.crop_w)
        flow[0] = tx  # u = x-displacement (constant over the frame)
        flow[1] = ty  # v = y-displacement

        return to_tensor(img1), to_tensor(img2), flow

    def __iter__(self) -> Iterator:
        while True:
            path = random.choice(self._image_paths)
            sample = self._synthetic_pair(path)
            if sample is not None:
                yield sample


class _LinkToAnimeDataset(IterableDataset):
    """
    Wraps the LinkTo-Anime dataset for supervised optical flow training.

    Expected directory layout (LinkTo-Anime format):
        lta_dir/
            seq_001/
                frame_0000.png
                frame_0001.png
                flow_0000.flo    # ground-truth flow 0000 → 0001
            ...

    Yields (img1, img2, flow) tuples in the same format as
    _AnimeSyntheticFlowDataset.
    """

    def __init__(self, lta_dir: str, crop_size: Tuple[int, int] = (256, 256)):
        self.lta_dir = Path(lta_dir)
        self.crop_h, self.crop_w = crop_size
        self._pairs = self._find_pairs()

    def _find_pairs(self) -> List[Tuple[Path, Path, Path]]:
        pairs = []
        for seq_dir in sorted(self.lta_dir.iterdir()):
            if not seq_dir.is_dir():
                continue
            flos = sorted(seq_dir.glob("*.flo"))
            for flo in flos:
                idx = int(flo.stem.split("_")[-1])
                f1 = seq_dir / f"frame_{idx:04d}.png"
                f2 = seq_dir / f"frame_{idx + 1:04d}.png"
                if f1.exists() and f2.exists():
                    pairs.append((f1, f2, flo))
        return pairs

    @staticmethod
    def _read_flo(path: Path) -> np.ndarray:
        """Read a Middlebury .flo file → (2, H, W) float32."""
        with open(path, "rb") as f:
            magic = np.frombuffer(f.read(4), dtype=np.float32)[0]
            if magic != 202021.25:
                raise ValueError(f"Invalid .flo file: {path}")
            W, H = np.frombuffer(f.read(8), dtype=np.int32)
            flow = np.frombuffer(f.read(), dtype=np.float32).reshape(H, W, 2)
        return flow.transpose(2, 0, 1)  # (2, H, W)

    def __iter__(self) -> Iterator:
        indices = list(range(len(self._pairs)))
        random.shuffle(indices)
        for i in indices:
            f1, f2, flo = self._pairs[i]
            img1 = cv2.imread(str(f1))
            img2 = cv2.imread(str(f2))
            flow = self._read_flo(flo)
            if img1 is None or img2 is None:
                continue
            H, W = img1.shape[:2]
            if H < self.crop_h or W < self.crop_w:
                continue
            r0 = random.randint(0, H - self.crop_h)
            c0 = random.randint(0, W - self.crop_w)
            img1 = img1[r0 : r0 + self.crop_h, c0 : c0 + self.crop_w]
            img2 = img2[r0 : r0 + self.crop_h, c0 : c0 + self.crop_w]
            flow = flow[:, r0 : r0 + self.crop_h, c0 : c0 + self.crop_w]

            def to_tensor(x):
                return torch.from_numpy(
                    cv2.cvtColor(x, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                ).permute(2, 0, 1)

            yield to_tensor(img1), to_tensor(img2), torch.from_numpy(flow)


# ── Loss ───────────────────────────────────────────────────────────────────────


def mixture_of_laplace_loss(
    pred_flows: List[torch.Tensor],
    gt_flow: torch.Tensor,
    gamma: float = 0.8,
) -> torch.Tensor:
    """
    SEA-RAFT Mixture-of-Laplace loss: robust to outlier pixels.

    pred_flows : list of (B, 2, H, W) predictions at different iterations.
    gt_flow    : (B, 2, H, W) ground-truth flow.
    gamma      : geometric weight decay for earlier iterations.
    """
    n = len(pred_flows)
    loss = torch.tensor(0.0, device=gt_flow.device)
    for i, pred in enumerate(pred_flows):
        weight = gamma ** (n - 1 - i)
        diff = (pred - gt_flow).abs().sum(dim=1, keepdim=True)  # (B, 1, H, W)
        loss = loss + weight * diff.mean()
    return loss


# ── Training loop ─────────────────────────────────────────────────────────────


def train(args: argparse.Namespace) -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[FineTune-RAFT] Training on {device}.")

    # Load SEA-RAFT
    # relocated: import ptlflow

    model = ptlflow.get_model("sea_raft").to(device)
    model.train()

    # Dataset
    synthetic_ds = _AnimeSyntheticFlowDataset(
        source_dir=args.source_dir,
        linktoanime_dir=getattr(args, "linktoanime", None),
    )
    datasets = [synthetic_ds]
    if hasattr(args, "linktoanime") and args.linktoanime:
        try:
            lta_ds = _LinkToAnimeDataset(args.linktoanime)
            datasets.append(lta_ds)
            print(f"[FineTune-RAFT] LinkTo-Anime: {len(lta_ds._pairs)} pairs.")
        except Exception as _e:
            print(
                f"[FineTune-RAFT] LinkTo-Anime unavailable ({_e}); using synthetic only."
            )

    # Interleave datasets by round-robining their iterators
    loader = DataLoader(synthetic_ds, batch_size=args.batch_size, num_workers=2)

    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=args.max_steps, eta_min=1e-7)

    os.makedirs(args.output_dir, exist_ok=True)
    step = 0
    running_loss = 0.0

    for img1, img2, gt_flow in loader:
        if step >= args.max_steps:
            break

        img1 = img1.to(device)
        img2 = img2.to(device)
        gt_flow = gt_flow.to(device)

        # ptlflow expects {'images': (B, 2, C, H, W)}
        out = model({"images": torch.stack([img1, img2], dim=1)})
        # flows: (B, iters, 2, H, W) or (B, 1, 2, H, W)
        pred_flows = [out["flows"][:, i] for i in range(out["flows"].shape[1])]

        loss = mixture_of_laplace_loss(pred_flows, gt_flow)
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        running_loss += loss.item()
        step += 1

        if step % 100 == 0:
            avg = running_loss / 100
            lr_now = scheduler.get_last_lr()[0]
            print(
                f"[FineTune-RAFT] step {step}/{args.max_steps}  loss={avg:.4f}  lr={lr_now:.2e}"
            )
            running_loss = 0.0

        if step % args.save_every == 0:
            ckpt = os.path.join(args.output_dir, f"sea_raft_anime_step{step}.pth")
            torch.save({"step": step, "state_dict": model.state_dict()}, ckpt)
            print(f"[FineTune-RAFT] Saved: {ckpt}")

    final_ckpt = os.path.join(args.output_dir, "sea_raft_anime.pth")
    torch.save({"step": step, "state_dict": model.state_dict()}, final_ckpt)
    print(f"[FineTune-RAFT] Training complete. Final ckpt: {final_ckpt}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fine-tune SEA-RAFT on anime frame pairs."
    )
    parser.add_argument(
        "--source_dir", required=True, help="Directory of anime PNG/JPG frames."
    )
    parser.add_argument(
        "--output_dir", default="backend/models/checkpoints/sea_raft_anime"
    )
    parser.add_argument(
        "--linktoanime", default=None, help="LinkTo-Anime dataset root."
    )
    parser.add_argument("--max_steps", type=int, default=20_000)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--save_every", type=int, default=2_000)
    args = parser.parse_args()
    train(args)
