"""Fine-tuner for CBIR (Content-Based Image Retrieval) embedding models.

Trains an image encoder + projection head via self-supervised metric learning.
No image labels are required — augmented views of the same image serve as
positive pairs.

Supported loss functions
------------------------
* **InfoNCE** (NT-Xent / SimCLR) — contrastive loss on in-batch negatives.
  Scales well and typically outperforms triplet loss at batch_size ≥ 64.
* **TripletMargin** — classic triplet loss with random in-batch negatives.
  Useful when GPU memory limits batch size below ~32.

Supported backbones
-------------------
* ``"clip"``        — CLIP ViT-B/32 vision encoder (HuggingFace transformers).
* ``"resnet50"``    — ResNet-50 (torchvision, ImageNet weights).
* ``"efficientnet"``— EfficientNet-V2-S (torchvision, ImageNet weights).

All backbones share the same projection-head interface and emit L2-normalised
embeddings.

Checkpoint format (saved with :meth:`CBIRTuner.save_checkpoint`)::

    {
        "config":          { ... training config dict ... },
        "model_state_dict": model.state_dict(),
        "epoch":           int,
        "best_recall_at_1": float,
    }

The checkpoint is loadable by ``backend.src.models.tuning.cbir_index_builder`` for
FAISS index construction.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

from backend.src.models.data.cbir_dataset import make_cbir_datasets

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cancel flag (matches StitchTrainer pattern for GUI integration)
# ---------------------------------------------------------------------------

class CBIRTuner:
    """Fine-tunes an image embedding model for reverse-image-search retrieval.

    Args:
        config: Training configuration dict (see :meth:`default_config`).
        on_log: Callback receiving a log message string.
        on_metrics: Callback receiving a per-step metrics dict.
        on_epoch_end: Callback receiving ``(epoch: int, metrics: dict)``.
    """

    is_cancelled: bool = False

    def __init__(
        self,
        config: dict,
        on_log: Optional[Callable[[str], None]] = None,
        on_metrics: Optional[Callable[[Dict], None]] = None,
        on_epoch_end: Optional[Callable[[int, Dict], None]] = None,
    ) -> None:
        self.config = {**self.default_config(), **config}
        self._log = on_log or (lambda m: None)
        self._metrics = on_metrics or (lambda m: None)
        self._epoch_end = on_epoch_end or (lambda e, m: None)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @classmethod
    def cancel(cls) -> None:
        """Request cancellation from any thread."""
        cls.is_cancelled = True

    @staticmethod
    def default_config() -> dict:
        """Return sensible defaults for all configuration keys."""
        return {
            "image_dir": "",
            "output_dir": "cbir_checkpoints",
            "val_split": 0.10,
            "backbone": "clip",           # "clip" | "resnet50" | "efficientnet"
            "embed_dim": 256,             # projection head output dimension
            "proj_layers": 2,             # number of linear layers in projection head
            "freeze_backbone_epochs": 2,  # unfreeze backbone after N warm-up epochs
            "loss_fn": "infonce",         # "infonce" | "triplet"
            "temperature": 0.07,          # InfoNCE temperature τ
            "triplet_margin": 0.3,        # TripletMarginLoss margin
            "epochs": 20,
            "batch_size": 64,
            "lr": 3e-4,
            "backbone_lr_scale": 0.1,     # backbone LR = lr × scale (after unfreeze)
            "warmup_epochs": 2,
            "num_workers": 4,
            "amp": True,
            "image_size": 224,
            "jitter_strength": 0.5,
            "seed": 42,
        }

    def train(self) -> None:
        """Run the full training loop.

        Raises:
            FileNotFoundError: If ``config["image_dir"]`` contains no images.
            ImportError: If a required dependency (torch, transformers, etc.)
                is not installed.
        """
        CBIRTuner.is_cancelled = False
        cfg = self.config
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._log(f"Device: {device} | backbone: {cfg['backbone']} | loss: {cfg['loss_fn']}")

        # ── Datasets & loaders ────────────────────────────────────────────
        use_triplet = cfg["loss_fn"] == "triplet"
        train_ds, val_ds = make_cbir_datasets(
            image_dir=cfg["image_dir"],
            val_split=cfg["val_split"],
            image_size=cfg["image_size"],
            backbone=cfg["backbone"],
            jitter_strength=cfg["jitter_strength"],
            return_triplet=use_triplet,
            seed=cfg["seed"],
        )
        self._log(f"Dataset: {len(train_ds)} train / {len(val_ds)} val images")

        train_loader = DataLoader(
            train_ds,
            batch_size=cfg["batch_size"],
            shuffle=True,
            num_workers=cfg["num_workers"],
            pin_memory=device.type == "cuda",
            drop_last=True,
        )
        val_loader = DataLoader(
            val_ds,
            batch_size=cfg["batch_size"],
            shuffle=False,
            num_workers=cfg["num_workers"],
            pin_memory=device.type == "cuda",
        )

        # ── Model ─────────────────────────────────────────────────────────
        model = _build_model(
            backbone=cfg["backbone"],
            embed_dim=cfg["embed_dim"],
            proj_layers=cfg["proj_layers"],
        ).to(device)

        # Freeze backbone parameters initially
        _set_backbone_frozen(model, True)
        self._log(f"Backbone frozen for first {cfg['freeze_backbone_epochs']} epochs")

        # ── Loss ──────────────────────────────────────────────────────────
        if cfg["loss_fn"] == "infonce":
            criterion = _InfoNCELoss(temperature=cfg["temperature"])
        else:
            criterion = nn.TripletMarginLoss(margin=cfg["triplet_margin"], p=2)
        criterion = criterion.to(device)

        # ── Optimiser — two parameter groups ──────────────────────────────
        head_params = list(model.projection.parameters())
        backbone_params = [p for p in model.backbone.parameters() if p.requires_grad]

        optimizer = torch.optim.AdamW(
            [
                {"params": head_params, "lr": cfg["lr"]},
                {"params": backbone_params, "lr": cfg["lr"] * cfg["backbone_lr_scale"]},
            ],
            weight_decay=1e-4,
        )

        total_steps = cfg["epochs"] * len(train_loader)
        warmup_steps = cfg["warmup_epochs"] * len(train_loader)
        scheduler = _CosineWithWarmup(optimizer, warmup_steps, total_steps)

        scaler = torch.cuda.amp.GradScaler(enabled=cfg["amp"] and device.type == "cuda")

        best_r1 = 0.0
        output_dir = Path(cfg["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        # ── Training loop ─────────────────────────────────────────────────
        for epoch in range(1, cfg["epochs"] + 1):
            if CBIRTuner.is_cancelled:
                self._log("Training cancelled by user.")
                break

            # Unfreeze backbone after warm-up
            if epoch == cfg["freeze_backbone_epochs"] + 1:
                _set_backbone_frozen(model, False)
                self._log(f"Epoch {epoch}: backbone unfrozen")

            train_loss = self._train_epoch(
                model, train_loader, criterion, optimizer, scheduler,
                scaler, device, epoch, cfg,
            )

            r1, r5, r10 = self._validate(model, val_loader, device)

            metrics = {
                "total": train_loss,
                "recall_at_1": r1,
                "recall_at_5": r5,
                "recall_at_10": r10,
                "epoch": epoch,
            }
            self._log(
                f"Epoch {epoch}/{cfg['epochs']} | loss={train_loss:.4f} | "
                f"R@1={r1:.3f} R@5={r5:.3f} R@10={r10:.3f}"
            )
            self._epoch_end(epoch, metrics)

            # Save best checkpoint
            if r1 >= best_r1:
                best_r1 = r1
                ckpt_path = output_dir / "cbir_best.pt"
                self.save_checkpoint(model, ckpt_path, epoch, best_r1)
                self._log(f"  ✓ Best checkpoint saved (R@1={best_r1:.3f})")

        # Always save the final model
        final_path = output_dir / "cbir_final.pt"
        self.save_checkpoint(model, final_path, cfg["epochs"], best_r1)
        self._log(f"Final checkpoint: {final_path}")

    def save_checkpoint(
        self,
        model: nn.Module,
        path: Path,
        epoch: int,
        best_recall_at_1: float,
    ) -> None:
        """Serialise model weights + config to *path*."""
        torch.save(
            {
                "config": self.config,
                "model_state_dict": model.state_dict(),
                "epoch": epoch,
                "best_recall_at_1": best_recall_at_1,
            },
            path,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _train_epoch(
        self,
        model: nn.Module,
        loader: DataLoader,
        criterion: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler,
        scaler: torch.cuda.amp.GradScaler,
        device: torch.device,
        epoch: int,
        cfg: dict,
    ) -> float:
        model.train()
        total_loss = 0.0
        amp_enabled = cfg["amp"] and device.type == "cuda"
        use_triplet = cfg["loss_fn"] == "triplet"

        for step, batch in enumerate(loader):
            if CBIRTuner.is_cancelled:
                break

            if use_triplet:
                a, p, n = [t.to(device, non_blocking=True) for t in batch]
                with torch.cuda.amp.autocast(enabled=amp_enabled):
                    ea = model(a)
                    ep = model(p)
                    en = model(n)
                    loss = criterion(ea, ep, en)
            else:
                v1, v2 = [t.to(device, non_blocking=True) for t in batch]
                with torch.cuda.amp.autocast(enabled=amp_enabled):
                    z1 = model(v1)
                    z2 = model(v2)
                    loss = criterion(z1, z2)

            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()

            loss_val = loss.item()
            total_loss += loss_val
            self._metrics({"total": loss_val, "step": (epoch - 1) * len(loader) + step})

        n = max(len(loader), 1)
        return total_loss / n

    @torch.no_grad()
    def _validate(
        self,
        model: nn.Module,
        loader: DataLoader,
        device: torch.device,
    ) -> Tuple[float, float, float]:
        """Compute Recall@1/5/10 using augmented pairs as ground truth.

        For each sample, view_a is the query; view_b is the positive.
        We embed both, build a FAISS-style inner-product matrix, and measure
        whether the paired view is within the top-K retrieved results.
        """
        model.eval()
        a_embs, b_embs = [], []
        for batch in loader:
            if len(batch) == 2:
                v1, v2 = batch
            else:
                v1, v2, _ = batch
            a_embs.append(model(v1.to(device)).cpu())
            b_embs.append(model(v2.to(device)).cpu())

        A = torch.cat(a_embs, dim=0)   # (N, D)
        B = torch.cat(b_embs, dim=0)   # (N, D) — positive pairs
        N = A.size(0)
        if N < 2:
            return 0.0, 0.0, 0.0

        # Cosine similarity matrix of queries A against gallery B
        sim = A @ B.T   # (N, N) — already L2-normalised so this is cosine

        r1 = r5 = r10 = 0
        for i in range(N):
            row = sim[i]
            # Diagonal = correct pair; retrieve top-K (excluding self)
            row[i] = -float("inf")
            ranked = row.argsort(descending=True)
            target_rank = int((ranked == i).nonzero(as_tuple=True)[0][0]) + 1
            if target_rank <= 1:
                r1 += 1
            if target_rank <= 5:
                r5 += 1
            if target_rank <= 10:
                r10 += 1

        return r1 / N, r5 / N, r10 / N


# ---------------------------------------------------------------------------
# Model building
# ---------------------------------------------------------------------------

class _ProjectionHead(nn.Module):
    """MLP projection head mapping backbone features → L2-normalised embedding."""

    def __init__(self, in_dim: int, out_dim: int, n_layers: int = 2) -> None:
        super().__init__()
        layers: List[nn.Module] = []
        hidden = max(in_dim, out_dim)
        for i in range(n_layers):
            d_in = in_dim if i == 0 else hidden
            d_out = out_dim if i == n_layers - 1 else hidden
            layers.append(nn.Linear(d_in, d_out, bias=False))
            if i < n_layers - 1:
                layers.append(nn.BatchNorm1d(d_out))
                layers.append(nn.ReLU(inplace=True))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return F.normalize(self.net(x), dim=-1)


class CBIRModel(nn.Module):
    """Image encoder + projection head.

    Args:
        backbone: Feature extractor module.  Should accept a
            ``[B, C, H, W]`` tensor and return ``[B, backbone_dim]``.
        backbone_dim: Output feature dimension of the backbone.
        embed_dim: Target embedding dimension (projection head output).
        proj_layers: Number of linear layers in the projection head.
    """

    def __init__(
        self,
        backbone: nn.Module,
        backbone_dim: int,
        embed_dim: int,
        proj_layers: int,
    ) -> None:
        super().__init__()
        self.backbone = backbone
        self.projection = _ProjectionHead(backbone_dim, embed_dim, proj_layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.backbone(x)
        return self.projection(features)


def _build_model(backbone: str, embed_dim: int, proj_layers: int) -> CBIRModel:
    """Construct a :class:`CBIRModel` for the given backbone identifier.

    Args:
        backbone: ``"clip"``, ``"resnet50"``, or ``"efficientnet"``.
        embed_dim: Projection head output dimension.
        proj_layers: Number of MLP layers in the projection head.

    Returns:
        A freshly constructed :class:`CBIRModel`.

    Raises:
        ValueError: For unknown backbone strings.
        ImportError: If required packages are missing.
    """
    if backbone == "clip":
        return _build_clip(embed_dim, proj_layers)
    if backbone == "resnet50":
        return _build_resnet50(embed_dim, proj_layers)
    if backbone == "efficientnet":
        return _build_efficientnet(embed_dim, proj_layers)
    raise ValueError(f"Unknown backbone: {backbone!r}")


def _build_clip(embed_dim: int, proj_layers: int) -> CBIRModel:
    try:
        from transformers import CLIPVisionConfig, CLIPVisionModel
    except ImportError as exc:
        raise ImportError(
            "transformers>=4.30 required for CLIP backbone.  "
            "Add 'transformers>=4.57.2' to pyproject.toml."
        ) from exc

    class _CLIPEncoder(nn.Module):
        def __init__(self):
            super().__init__()
            self.clip = CLIPVisionModel.from_pretrained("openai/clip-vit-base-patch32")

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            out = self.clip(pixel_values=x)
            return out.pooler_output  # (B, 768)

    encoder = _CLIPEncoder()
    return CBIRModel(encoder, backbone_dim=768, embed_dim=embed_dim, proj_layers=proj_layers)


def _build_resnet50(embed_dim: int, proj_layers: int) -> CBIRModel:
    import torchvision.models as tvm

    model = tvm.resnet50(weights=tvm.ResNet50_Weights.DEFAULT)
    backbone_dim = model.fc.in_features
    model.fc = nn.Identity()

    class _ResNetEncoder(nn.Module):
        def __init__(self, net):
            super().__init__()
            self.net = net

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x)

    return CBIRModel(_ResNetEncoder(model), backbone_dim=backbone_dim, embed_dim=embed_dim, proj_layers=proj_layers)


def _build_efficientnet(embed_dim: int, proj_layers: int) -> CBIRModel:
    import torchvision.models as tvm

    model = tvm.efficientnet_v2_s(weights=tvm.EfficientNet_V2_S_Weights.DEFAULT)
    backbone_dim = model.classifier[1].in_features
    model.classifier = nn.Identity()

    class _EffNetEncoder(nn.Module):
        def __init__(self, net):
            super().__init__()
            self.net = net

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.net(x)

    return CBIRModel(_EffNetEncoder(model), backbone_dim=backbone_dim, embed_dim=embed_dim, proj_layers=proj_layers)


def _set_backbone_frozen(model: CBIRModel, frozen: bool) -> None:
    for p in model.backbone.parameters():
        p.requires_grad = not frozen


# ---------------------------------------------------------------------------
# Loss functions
# ---------------------------------------------------------------------------

class _InfoNCELoss(nn.Module):
    """NT-Xent / SimCLR contrastive loss.

    Given two batches of L2-normalised embeddings ``z1`` and ``z2`` where
    pair ``(z1[i], z2[i])`` is positive, the loss maximises agreement between
    positive pairs and pushes apart all ``2(N-1)`` in-batch negatives.

    Args:
        temperature: Softmax temperature τ.  Lower values → sharper
            distribution.  Typical values: 0.05–0.2.
    """

    def __init__(self, temperature: float = 0.07) -> None:
        super().__init__()
        self.tau = temperature

    def forward(self, z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        N = z1.size(0)
        # Concatenate along batch dimension → 2N embeddings
        z = torch.cat([z1, z2], dim=0)  # (2N, D)
        sim = (z @ z.T) / self.tau      # (2N, 2N)

        # Mask out self-similarities on the diagonal
        mask = torch.eye(2 * N, device=z.device, dtype=torch.bool)
        sim = sim.masked_fill(mask, -1e9)

        # Positive pairs: (i, i+N) and (i+N, i)
        labels = torch.cat([torch.arange(N, 2 * N), torch.arange(0, N)]).to(z.device)
        return F.cross_entropy(sim, labels)


# ---------------------------------------------------------------------------
# LR scheduler: cosine with linear warmup
# ---------------------------------------------------------------------------

class _CosineWithWarmup:
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        warmup_steps: int,
        total_steps: int,
    ) -> None:
        self._opt = optimizer
        self._warmup = max(warmup_steps, 1)
        self._total = max(total_steps, warmup_steps + 1)
        self._step = 0
        self._base_lrs = [pg["lr"] for pg in optimizer.param_groups]

    def step(self) -> None:
        self._step += 1
        s = self._step
        if s < self._warmup:
            scale = s / self._warmup
        else:
            progress = (s - self._warmup) / (self._total - self._warmup)
            scale = 0.5 * (1.0 + math.cos(math.pi * progress))
        for pg, base_lr in zip(self._opt.param_groups, self._base_lrs, strict=False):
            pg["lr"] = base_lr * scale
