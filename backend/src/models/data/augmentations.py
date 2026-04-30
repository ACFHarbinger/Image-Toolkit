"""
backend/src/models/data/augmentations.py
=========================================
Anime-specific data augmentations for diffusion LoRA training.

All augmentations accept a CHW float32 tensor in [-1, 1] and an optional
binary foreground mask (same spatial dims, [0,1] float).

The foreground mask is produced by BiRefNetWrapper and isolates the character
from the background, enabling mask-aware transforms that preserve character
identity (hair/eye colour, etc.).

Augmentations
-------------
FgPreservingHueJitter   — hue-shift only background pixels
CharacterAwareCrop      — reject crops that clip the character
BackgroundSwap          — blend character over random background image
RandomErasingFg         — erase patches inside the character bounding box
BroadcastDimCurve       — simulate TV broadcast dimming artefact
MotionBlurSim           — simulate camera motion blur
MPEGBlockNoise          — simulate MPEG compression block noise
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torchvision.transforms.functional as TF
from PIL import Image


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class AnimeAugmentation:
    def __call__(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1. Cel-shade-preserving colour jitter
# ---------------------------------------------------------------------------
class FgPreservingHueJitter(AnimeAugmentation):
    """
    Shift hue only in background pixels (mask == 0).
    Preserves character hair/eye colour identity, which is a critical
    feature-binding signal for character LoRAs.
    """

    def __init__(self, max_shift: float = 0.06):
        self.max_shift = max_shift

    def __call__(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if mask is None:
            return x
        shift = (random.random() * 2 - 1) * self.max_shift
        # x is in [-1,1] — move to [0,1] for HSV conversion
        x01 = x * 0.5 + 0.5
        hsv = TF.rgb_to_hsv(x01)          # (3,H,W) hue in [0,1]
        bg_mask = (1.0 - mask.float()).clamp(0, 1)  # (1,H,W) or (H,W)
        if bg_mask.dim() == 2:
            bg_mask = bg_mask.unsqueeze(0)
        hsv[0] = (hsv[0] + shift * bg_mask.squeeze(0)) % 1.0
        return TF.hsv_to_rgb(hsv) * 2.0 - 1.0


# ---------------------------------------------------------------------------
# 2. Character-aware random crop
# ---------------------------------------------------------------------------
class CharacterAwareCrop(AnimeAugmentation):
    """
    Random crop that ensures the foreground area is ≥ min_fg_retain of its
    uncropped value.  Falls back to centre-crop after max_tries failures.
    """

    def __init__(
        self,
        crop_size: int,
        min_fg_retain: float = 0.30,
        max_tries: int = 5,
    ):
        self.crop_size = crop_size
        self.min_fg_retain = min_fg_retain
        self.max_tries = max_tries

    def __call__(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        _, H, W = x.shape
        cs = self.crop_size
        if H < cs or W < cs:
            return TF.center_crop(x, cs)

        fg_total = mask.sum().item() if mask is not None else 1.0

        for _ in range(self.max_tries):
            top = random.randint(0, H - cs)
            left = random.randint(0, W - cs)
            if mask is not None:
                patch_mask = mask[..., top:top + cs, left:left + cs]
                if patch_mask.sum().item() >= self.min_fg_retain * fg_total:
                    return x[:, top:top + cs, left:left + cs]
            else:
                return x[:, top:top + cs, left:left + cs]

        # Fallback
        return TF.center_crop(x, cs)


# ---------------------------------------------------------------------------
# 3. Background swap
# ---------------------------------------------------------------------------
class BackgroundSwap(AnimeAugmentation):
    """
    With probability `p`, composite the foreground character over a random
    background drawn from `bg_paths`.  This is the single largest diversity
    win for character LoRAs trained on a small dataset.
    """

    def __init__(
        self,
        bg_paths: list[Path],
        p: float = 0.10,
        blend_alpha: float = 1.0,
    ):
        self.bg_paths = bg_paths
        self.p = p
        self.blend_alpha = blend_alpha

    def __call__(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if mask is None or not self.bg_paths or random.random() > self.p:
            return x
        _, H, W = x.shape
        bg_path = random.choice(self.bg_paths)
        try:
            with Image.open(bg_path) as bg_im:
                bg_im = bg_im.convert("RGB").resize((W, H), Image.LANCZOS)
            bg = TF.to_tensor(bg_im) * 2.0 - 1.0   # [-1,1] CHW
        except Exception:
            return x

        fg_mask = mask.float()
        if fg_mask.dim() == 2:
            fg_mask = fg_mask.unsqueeze(0)
        return x * fg_mask + bg * (1.0 - fg_mask)


# ---------------------------------------------------------------------------
# 4. Random erasing inside character bounding box
# ---------------------------------------------------------------------------
class RandomErasingFg(AnimeAugmentation):
    """
    Erase 8–24 % of image area but only inside the character bounding box.
    Teaches inpainting of the character and reduces memorization.
    """

    def __init__(self, p: float = 0.15, min_area: float = 0.08, max_area: float = 0.24):
        self.p = p
        self.min_area = min_area
        self.max_area = max_area

    def __call__(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if random.random() > self.p or mask is None:
            return x
        _, H, W = x.shape
        fg = mask.float()
        if fg.dim() == 3:
            fg = fg.squeeze(0)
        rows = fg.any(dim=1).nonzero(as_tuple=True)[0]
        cols = fg.any(dim=0).nonzero(as_tuple=True)[0]
        if len(rows) < 4 or len(cols) < 4:
            return x
        r0, r1 = int(rows[0]), int(rows[-1])
        c0, c1 = int(cols[0]), int(cols[-1])
        box_h, box_w = r1 - r0, c1 - c0
        area = H * W * random.uniform(self.min_area, self.max_area)
        eh = int((area * random.uniform(0.3, 1.0 / 0.3)) ** 0.5)
        ew = int(area / eh)
        eh, ew = min(eh, box_h), min(ew, box_w)
        if eh < 1 or ew < 1:
            return x
        top = random.randint(r0, max(r0, r1 - eh))
        left = random.randint(c0, max(c0, c1 - ew))
        x = x.clone()
        x[:, top:top + eh, left:left + ew] = 0.0
        return x


# ---------------------------------------------------------------------------
# 5. Broadcast dim curve (simulate TV capture brightness artefact)
# ---------------------------------------------------------------------------
class BroadcastDimCurve(AnimeAugmentation):
    """Simulate the non-linear brightness curve of broadcast TV captures."""

    def __init__(self, p: float = 0.20, max_dim: float = 0.15):
        self.p = p
        self.max_dim = max_dim

    def __call__(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if random.random() > self.p:
            return x
        factor = 1.0 - random.random() * self.max_dim
        return (x * factor).clamp(-1.0, 1.0)


# ---------------------------------------------------------------------------
# 6. Motion blur simulation
# ---------------------------------------------------------------------------
class MotionBlurSim(AnimeAugmentation):
    """Simulate horizontal/vertical camera motion blur."""

    def __init__(self, p: float = 0.10, max_kernel: int = 7):
        self.p = p
        self.max_kernel = max_kernel

    def __call__(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if random.random() > self.p:
            return x
        import torch.nn.functional as F
        k = random.choice(range(3, self.max_kernel + 1, 2))
        kernel = torch.zeros(1, 1, k, k, dtype=x.dtype, device=x.device)
        if random.random() < 0.5:
            kernel[0, 0, k // 2, :] = 1.0 / k   # horizontal
        else:
            kernel[0, 0, :, k // 2] = 1.0 / k   # vertical
        kernel = kernel.repeat(3, 1, 1, 1)
        blurred = F.conv2d(
            x.unsqueeze(0), kernel, padding=k // 2, groups=3
        ).squeeze(0)
        return blurred.clamp(-1.0, 1.0)


# ---------------------------------------------------------------------------
# 7. MPEG block noise
# ---------------------------------------------------------------------------
class MPEGBlockNoise(AnimeAugmentation):
    """Simulate MPEG compression block artefacts (8×8 pixel blocks)."""

    def __init__(self, p: float = 0.10, severity: float = 0.05):
        self.p = p
        self.severity = severity

    def __call__(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if random.random() > self.p:
            return x
        _, H, W = x.shape
        noise = torch.zeros_like(x)
        for r in range(0, H, 8):
            for c in range(0, W, 8):
                block_noise = (torch.rand(3, 1, 1, device=x.device) - 0.5) * self.severity
                noise[:, r:r + 8, c:c + 8] = block_noise
        return (x + noise).clamp(-1.0, 1.0)


# ---------------------------------------------------------------------------
# Default augmentation stack factory
# ---------------------------------------------------------------------------
def default_anime_augmentations(
    bg_paths: Optional[list[Path]] = None,
    crop_size: Optional[int] = None,
) -> list[AnimeAugmentation]:
    """
    Returns the recommended augmentation stack for anime character LoRAs.
    Ordering: photometric → spatial → structural.
    """
    augs: list[AnimeAugmentation] = [
        BroadcastDimCurve(p=0.20),
        FgPreservingHueJitter(max_shift=0.06),
        MPEGBlockNoise(p=0.10),
        MotionBlurSim(p=0.10),
    ]
    if bg_paths:
        augs.append(BackgroundSwap(bg_paths=bg_paths, p=0.10))
    if crop_size is not None:
        augs.append(CharacterAwareCrop(crop_size=crop_size))
    augs.append(RandomErasingFg(p=0.15))
    return augs
