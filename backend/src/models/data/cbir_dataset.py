"""Self-supervised pair dataset for CBIR metric-learning fine-tuning.

Each __getitem__ returns two differently-augmented views of the same image
(SimCLR / NT-Xent protocol).  For triplet training a third ``negative`` view
drawn from a *different* image is appended.

Augmentation philosophy for CBIR:
  • Preserve enough content that the model learns visual identity, not
    colour-invariance.  Avoid extreme geometric distortions.
  • Colour jitter moderate (not as heavy as classification tasks).
  • Random resized crop retains 60-100 % of the image area.
  • Gaussian blur softens JPEG artefacts; helps cross-resolution retrieval.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

log = logging.getLogger(__name__)

_IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


# ---------------------------------------------------------------------------
# Augmentation factory
# ---------------------------------------------------------------------------

def make_cbir_augmentation(
    image_size: int = 224,
    jitter_strength: float = 0.5,
    blur_prob: float = 0.3,
    grayscale_prob: float = 0.1,
) -> transforms.Compose:
    """Return a torchvision transform pipeline suitable for CBIR training.

    Args:
        image_size: Square output resolution (default 224 for ViT/ResNet).
        jitter_strength: Scale factor for colour-jitter magnitude.  0 = off.
        blur_prob: Probability of applying Gaussian blur.
        grayscale_prob: Probability of converting to greyscale (3-channel).

    Returns:
        A ``transforms.Compose`` that maps ``PIL.Image → torch.Tensor [C,H,W]``
        in ``[0, 1]`` float32 (compatible with both CLIP and ImageNet norms).
    """
    s = jitter_strength
    aug_list = [
        transforms.RandomResizedCrop(image_size, scale=(0.60, 1.0), ratio=(0.75, 1.33)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomApply(
            [transforms.ColorJitter(0.8 * s, 0.8 * s, 0.4 * s, 0.1 * s)],
            p=0.8,
        ),
        transforms.RandomGrayscale(p=grayscale_prob),
    ]
    if blur_prob > 0:
        aug_list.append(
            transforms.RandomApply(
                [transforms.GaussianBlur(kernel_size=23, sigma=(0.1, 2.0))],
                p=blur_prob,
            )
        )
    aug_list.append(transforms.ToTensor())
    return transforms.Compose(aug_list)


def make_clip_preprocess(image_size: int = 224) -> transforms.Compose:
    """Return the standard CLIP pre-process (normalised to CLIP stats)."""
    return transforms.Compose([
        transforms.Resize(image_size, interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.CenterCrop(image_size),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=(0.48145466, 0.4578275, 0.40821073),
            std=(0.26862954, 0.26130258, 0.27577711),
        ),
    ])


def make_imagenet_preprocess(image_size: int = 224) -> transforms.Compose:
    """Return the standard ImageNet pre-process (for ResNet / EfficientNet)."""
    return transforms.Compose([
        transforms.Resize(image_size, interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.CenterCrop(image_size),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class CBIRPairDataset(Dataset):
    """Returns augmented image pairs ``(view_a, view_b)`` for contrastive training.

    Both views originate from the **same** source image, making them positives.
    For triplet training set ``return_triplet=True``; a negative drawn from a
    *different* random image is appended as the third element.

    Args:
        image_paths: List of absolute paths to training images.
        augment: Transform applied independently to each view.  Should produce
            a ``[C,H,W]`` float tensor.
        return_triplet: If ``True`` return ``(anchor, positive, negative)``
            instead of ``(view_a, view_b)``.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        image_paths: List[str],
        augment: Callable,
        return_triplet: bool = False,
        seed: int = 42,
    ) -> None:
        self.paths = image_paths
        self.augment = augment
        self.return_triplet = return_triplet
        self._rng = random.Random(seed)

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int):
        img = self._load(self.paths[idx])
        view_a = self.augment(img)
        view_b = self.augment(img)

        if not self.return_triplet:
            return view_a, view_b

        # Negative: a different image
        neg_idx = self._rng.randint(0, len(self.paths) - 1)
        while neg_idx == idx and len(self.paths) > 1:
            neg_idx = self._rng.randint(0, len(self.paths) - 1)
        neg_img = self._load(self.paths[neg_idx])
        negative = self.augment(neg_img)
        return view_a, view_b, negative

    @staticmethod
    def _load(path: str) -> Image.Image:
        try:
            return Image.open(path).convert("RGB")
        except Exception as exc:
            log.warning("Could not load %s: %s — returning black image", path, exc)
            return Image.new("RGB", (224, 224), 0)


def scan_images(directory: str) -> List[str]:
    """Recursively collect image paths under *directory*.

    Args:
        directory: Root directory to scan.

    Returns:
        Sorted list of absolute path strings.
    """
    root = Path(directory)
    paths = [
        str(p.resolve())
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in _IMG_EXTENSIONS
    ]
    paths.sort()
    return paths


def make_cbir_datasets(
    image_dir: str,
    val_split: float = 0.10,
    image_size: int = 224,
    backbone: str = "clip",
    jitter_strength: float = 0.5,
    return_triplet: bool = False,
    seed: int = 42,
) -> Tuple[CBIRPairDataset, CBIRPairDataset]:
    """Scan *image_dir*, split into train/val, and return dataset objects.

    Args:
        image_dir: Root directory containing images.
        val_split: Fraction of images to hold out for validation.
        image_size: Spatial resolution fed to the model.
        backbone: One of ``"clip"``, ``"resnet50"``, ``"efficientnet"``.  Chooses
            the correct normalisation statistics for the base preprocess.
        jitter_strength: Passed to :func:`make_cbir_augmentation`.
        return_triplet: If ``True``, datasets yield triplets.
        seed: Random seed for reproducible splits.

    Returns:
        ``(train_dataset, val_dataset)`` pair.
    """
    paths = scan_images(image_dir)
    if not paths:
        raise FileNotFoundError(f"No images found under: {image_dir}")

    rng = random.Random(seed)
    shuffled = paths[:]
    rng.shuffle(shuffled)
    n_val = max(1, int(len(shuffled) * val_split))
    val_paths = shuffled[:n_val]
    train_paths = shuffled[n_val:]

    aug = make_cbir_augmentation(image_size=image_size, jitter_strength=jitter_strength)

    train_ds = CBIRPairDataset(train_paths, augment=aug, return_triplet=return_triplet, seed=seed)
    val_ds = CBIRPairDataset(val_paths, augment=aug, return_triplet=return_triplet, seed=seed + 1)
    return train_ds, val_ds
