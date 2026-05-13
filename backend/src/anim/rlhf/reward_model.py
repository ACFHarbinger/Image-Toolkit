"""
Learned reward model for stitched-image quality.

Architecture: lightweight CNN → AdaptiveAvgPool → MLP → sigmoid → [0, 1].

Training signal:
  • Whole-image score  → overall_rating / 10
  • Annotated patches  → penalised according to flaw severity
    target = max(0, rating/10 - severity * 0.5)

At inference time ``predict(img_bgr)`` returns a scalar in [0, 1] where
1.0 = perfect stitch and 0.0 = completely broken.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset, random_split

    _TORCH_OK = True
except ImportError:
    _TORCH_OK = False

from .feedback_store import FeedbackStore

_DEFAULT_MODEL_PATH = Path.home() / ".config" / "image-toolkit" / "stitch_reward_model.pt"
_INPUT_SIZE = 224


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------

if _TORCH_OK:

    class _RewardNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(3, 32, 3, stride=2, padding=1),   # 112
                nn.BatchNorm2d(32),
                nn.ReLU(inplace=True),
                nn.Conv2d(32, 64, 3, stride=2, padding=1),  # 56
                nn.BatchNorm2d(64),
                nn.ReLU(inplace=True),
                nn.Conv2d(64, 128, 3, stride=2, padding=1), # 28
                nn.BatchNorm2d(128),
                nn.ReLU(inplace=True),
                nn.Conv2d(128, 256, 3, stride=2, padding=1),# 14
                nn.BatchNorm2d(256),
                nn.ReLU(inplace=True),
                nn.AdaptiveAvgPool2d(4),                     # 4×4
            )
            self.head = nn.Sequential(
                nn.Flatten(),
                nn.Linear(256 * 16, 256),
                nn.ReLU(inplace=True),
                nn.Dropout(0.3),
                nn.Linear(256, 1),
                nn.Sigmoid(),
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            return self.head(self.features(x)).squeeze(-1)

else:

    class _RewardNet:  # type: ignore
        def __init__(self, *a, **kw):
            raise RuntimeError("torch is required for StitchRewardModel")


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def _load_bgr(path: str) -> Optional[np.ndarray]:
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    return img


def _bgr_to_tensor(img: np.ndarray, size: int = _INPUT_SIZE) -> "torch.Tensor":
    """Resize, convert BGR→RGB, normalize to [0,1], return (3,H,W) tensor."""
    resized = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    t = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1)
    return t


def _extract_patch(
    img: np.ndarray,
    x_n: float,
    y_n: float,
    w_n: float,
    h_n: float,
) -> Optional[np.ndarray]:
    H, W = img.shape[:2]
    x0 = max(0, int(x_n * W))
    y0 = max(0, int(y_n * H))
    x1 = min(W, int((x_n + w_n) * W))
    y1 = min(H, int((y_n + h_n) * H))
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    return img[y0:y1, x0:x1]


if _TORCH_OK:

    class _FeedbackDataset(Dataset):
        """Flat list of (tensor, target_quality) pairs built from FeedbackStore."""

        def __init__(self, records: List[Tuple["torch.Tensor", float]]):
            self._data = records

        def __len__(self) -> int:
            return len(self._data)

        def __getitem__(self, idx: int) -> Tuple["torch.Tensor", float]:
            return self._data[idx]

    def _build_dataset(store: FeedbackStore) -> "_FeedbackDataset":
        records: List[Tuple["torch.Tensor", float]] = []
        for fb in store:
            img = _load_bgr(fb.image_path)
            if img is None:
                continue
            # Whole-image sample
            t = _bgr_to_tensor(img)
            target = fb.overall_rating / 10.0
            records.append((t, float(target)))
            # Per-annotation samples
            for ann in fb.annotations:
                patch = _extract_patch(img, ann.x, ann.y, ann.w, ann.h)
                if patch is None:
                    continue
                pt = _bgr_to_tensor(patch)
                # Bad region: quality lower than overall, scaled by severity
                ann_target = max(0.0, target - ann.severity * 0.5)
                records.append((pt, float(ann_target)))
        return _FeedbackDataset(records)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class StitchRewardModel:
    """Wrapper around _RewardNet with train / predict / save / load."""

    def __init__(self, model_path: Optional[str] = None):
        if not _TORCH_OK:
            raise RuntimeError("torch is required for StitchRewardModel")
        self._path = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.net = _RewardNet().to(self.device)
        if self._path.exists():
            self._load()

    # ---------------------------------------------------------------- inference

    def predict(self, img_bgr: np.ndarray) -> float:
        """Predict quality of a stitched panorama patch, return [0, 1]."""
        t = _bgr_to_tensor(img_bgr).unsqueeze(0).to(self.device)
        self.net.eval()
        with torch.no_grad():
            return float(self.net(t).item())

    def predict_region(
        self,
        img_bgr: np.ndarray,
        x_n: float,
        y_n: float,
        w_n: float,
        h_n: float,
    ) -> float:
        """Predict quality of a specific normalized region."""
        patch = _extract_patch(img_bgr, x_n, y_n, w_n, h_n)
        if patch is None:
            return self.predict(img_bgr)
        return self.predict(patch)

    # ----------------------------------------------------------------- training

    def train_from_feedback(
        self,
        store: FeedbackStore,
        epochs: int = 20,
        lr: float = 1e-3,
        batch_size: int = 16,
        val_split: float = 0.15,
        progress_cb=None,
    ) -> List[float]:
        """
        Train (or fine-tune) the reward model from a FeedbackStore.

        Returns list of per-epoch validation losses.
        Calls ``progress_cb(epoch, n_epochs, val_loss)`` if provided.
        """
        dataset = _build_dataset(store)
        n = len(dataset)
        if n < 2:
            raise ValueError(f"Need at least 2 training samples, got {n}.")

        n_val = max(1, int(n * val_split))
        n_train = n - n_val
        train_ds, val_ds = random_split(dataset, [n_train, n_val])
        train_dl = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
        val_dl = DataLoader(val_ds, batch_size=batch_size)

        self.net.train()
        optim = torch.optim.Adam(self.net.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=epochs)
        val_losses: List[float] = []

        for ep in range(1, epochs + 1):
            self.net.train()
            for imgs, targets in train_dl:
                imgs = imgs.to(self.device)
                targets = targets.float().to(self.device)
                pred = self.net(imgs)
                loss = F.mse_loss(pred, targets)
                optim.zero_grad()
                loss.backward()
                optim.step()
            scheduler.step()

            self.net.eval()
            v_loss = 0.0
            with torch.no_grad():
                for imgs, targets in val_dl:
                    imgs = imgs.to(self.device)
                    targets = targets.float().to(self.device)
                    v_loss += F.mse_loss(self.net(imgs), targets).item()
            v_loss /= max(len(val_dl), 1)
            val_losses.append(v_loss)
            if progress_cb:
                progress_cb(ep, epochs, v_loss)

        self.save()
        return val_losses

    # ----------------------------------------------------------------- persist

    def save(self, path: Optional[str] = None) -> None:
        p = Path(path) if path else self._path
        p.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.net.state_dict(), p)

    def _load(self) -> None:
        state = torch.load(self._path, map_location=self.device, weights_only=True)
        self.net.load_state_dict(state)


__all__ = ["StitchRewardModel"]
