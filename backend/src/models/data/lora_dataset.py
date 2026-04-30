from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import torch
import torchvision.transforms.functional as TF
from PIL import Image
from torch.utils.data import Dataset, Sampler


# ---------------------------------------------------------------------------
# Legacy LoRADataset (preserved for backward compatibility)
# ---------------------------------------------------------------------------
class LoRADataset(Dataset):
    def __init__(
        self, root_dir, tokenizer, size=1024, trigger="my_char", pruned_tags=None
    ):
        self.root_dir = root_dir
        self.tokenizer = tokenizer
        self.size = size
        self.trigger = trigger
        self.pruned_tags = (
            [t.strip().lower() for t in pruned_tags.split(",")] if pruned_tags else []
        )

        self.image_paths = [
            os.path.join(root_dir, f)
            for f in os.listdir(root_dir)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]

    def __len__(self):
        return len(self.image_paths)

    def process_image(self, image: Image.Image) -> torch.Tensor:
        image = image.resize((self.size, self.size), Image.LANCZOS)
        t = TF.to_tensor(image)
        return t * 2.0 - 1.0

    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        image = Image.open(img_path).convert("RGB")

        # Load associated .txt file
        tag_path = os.path.splitext(img_path)[0] + ".txt"
        if os.path.exists(tag_path):
            with open(tag_path, "r") as f:
                tags = [t.strip() for t in f.read().split(",")]

            # Feature Binding: Filter out tags we want the trigger word to 'own'
            filtered_tags = [t for t in tags if t.lower() not in self.pruned_tags]
            caption = f"{self.trigger}, " + ", ".join(filtered_tags)
        else:
            caption = self.trigger

        # Process image and tokenize caption
        inputs = self.tokenizer(
            caption, padding="max_length", truncation=True, return_tensors="pt"
        )
        return {
            "pixel_values": self.process_image(image),
            "input_ids": inputs.input_ids[0],
        }


# ---------------------------------------------------------------------------
# SDXL aspect-ratio bucket definitions (kohya canonical set at ~1 MP)
# ---------------------------------------------------------------------------
SDXL_BUCKETS: tuple[tuple[int, int], ...] = (
    (1024, 1024),
    (1152, 896), (896, 1152),
    (1216, 832), (832, 1216),
    (1344, 768), (768, 1344),
    (1536, 640), (640, 1536),
    (1280, 768), (768, 1280),
    (1408, 704), (704, 1408),
)


def closest_bucket(w: int, h: int, buckets=SDXL_BUCKETS) -> tuple[int, int]:
    """Return the SDXL bucket whose aspect ratio is closest to w/h."""
    ar = w / max(h, 1)
    return min(
        buckets,
        key=lambda b: (abs(b[0] / b[1] - ar), abs(b[0] * b[1] - 1024 * 1024)),
    )


# ---------------------------------------------------------------------------
# BucketSample: metadata record for one training image
# ---------------------------------------------------------------------------
@dataclass
class BucketSample:
    image_path: Path
    caption: str                        # raw caption string (not tokenised)
    pruned_tags: list[str]              # ordered tag list (post-prune)
    bucket: tuple[int, int]             # (width, height) in pixels
    original_size: tuple[int, int]      # (width, height) of source image
    crop_top_left: tuple[int, int]      # (top, left) for SDXL micro-conditioning

    @classmethod
    def from_path(
        cls,
        image_path: Path,
        trigger: Optional[str] = None,
        pruned_tags: Optional[list[str]] = None,
        buckets: tuple[tuple[int, int], ...] = SDXL_BUCKETS,
    ) -> "BucketSample":
        with Image.open(image_path) as im:
            ow, oh = im.size
        bucket = closest_bucket(ow, oh, buckets)

        tags = pruned_tags or []
        txt = image_path.with_suffix(".txt")
        if txt.exists() and not pruned_tags:
            raw = txt.read_text(encoding="utf-8").strip()
            tags = [t.strip() for t in raw.split(",") if t.strip()]

        caption = (f"{trigger}, " + ", ".join(tags)) if trigger else ", ".join(tags)
        return cls(
            image_path=image_path,
            caption=caption,
            pruned_tags=tags,
            bucket=bucket,
            original_size=(ow, oh),
            crop_top_left=(0, 0),
        )


# ---------------------------------------------------------------------------
# Aspect-ratio bucket sampler
# ---------------------------------------------------------------------------
class AspectRatioBucketSampler(Sampler):
    """
    Yields batches where every sample in the batch shares the same (W, H)
    bucket.  This avoids padding waste and gives correct SDXL
    original_size / target_size micro-conditioning.
    """

    def __init__(
        self,
        samples: list[BucketSample],
        batch_size: int,
        drop_last: bool = True,
        seed: int = 0,
    ):
        self.batch_size = batch_size
        self.drop_last = drop_last
        self._rng = random.Random(seed)
        self._buckets: dict[tuple[int, int], list[int]] = {}
        for i, s in enumerate(samples):
            self._buckets.setdefault(s.bucket, []).append(i)

    def __len__(self) -> int:
        total = 0
        for idxs in self._buckets.values():
            n = len(idxs) // self.batch_size
            if not self.drop_last and len(idxs) % self.batch_size:
                n += 1
            total += n
        return total

    def __iter__(self):
        order = list(self._buckets.items())
        self._rng.shuffle(order)
        for _bk, idxs in order:
            idxs = list(idxs)
            self._rng.shuffle(idxs)
            for i in range(0, len(idxs), self.batch_size):
                batch = idxs[i: i + self.batch_size]
                if len(batch) == self.batch_size or not self.drop_last:
                    yield batch


# ---------------------------------------------------------------------------
# LoRADatasetV2 — SDXL bucketing + BiRefNet + BaSiC + augmentations
# ---------------------------------------------------------------------------
class LoRADatasetV2(Dataset):
    """
    Parameters
    ----------
    samples         : list of BucketSample (one per training image)
    tokenizer_one   : CLIP-L tokenizer
    tokenizer_two   : OpenCLIP-bigG tokenizer (None for SD1.5)
    trigger_word    : unique activation token (e.g. 'mychar_xyz')
    shuffle_tags    : randomly shuffle tags after keep_tokens head
    keep_tokens     : number of front tokens to keep pinned (trigger + class)
    caption_dropout : probability of zeroing the caption (CFG training)
    tag_dropout     : per-tag random drop probability
    birefnet        : BiRefNetWrapper instance for foreground masking
    basic           : BaSiCWrapper instance for photometric normalisation
    apply_basic_prob: probability of applying BaSiC correction per sample
    augmentations   : list of AnimeAugmentation instances
    """

    def __init__(
        self,
        samples: Sequence[BucketSample],
        tokenizer_one,
        tokenizer_two=None,
        trigger_word: Optional[str] = None,
        shuffle_tags: bool = True,
        keep_tokens: int = 1,
        caption_dropout: float = 0.05,
        tag_dropout: float = 0.0,
        birefnet=None,
        basic=None,
        apply_basic_prob: float = 0.5,
        augmentations: Optional[list] = None,
    ):
        self.samples = list(samples)
        self.tok1 = tokenizer_one
        self.tok2 = tokenizer_two
        self.trigger_word = trigger_word
        self.shuffle_tags = shuffle_tags
        self.keep_tokens = keep_tokens
        self.caption_dropout = caption_dropout
        self.tag_dropout = tag_dropout
        self.birefnet = birefnet
        self.basic = basic
        self.apply_basic_prob = apply_basic_prob
        self.augmentations = augmentations or []

    def __len__(self) -> int:
        return len(self.samples)

    # ------------------------------------------------------------------
    # Caption builder
    # ------------------------------------------------------------------
    def _build_caption(self, s: BucketSample) -> str:
        if random.random() < self.caption_dropout:
            return ""
        tags = list(s.pruned_tags)
        if self.shuffle_tags and len(tags) > self.keep_tokens:
            head, tail = tags[: self.keep_tokens], tags[self.keep_tokens:]
            random.shuffle(tail)
            tags = head + tail
        if self.tag_dropout > 0.0:
            pinned = set(tags[: self.keep_tokens])
            tags = [t for t in tags if t in pinned or random.random() > self.tag_dropout]
        if self.trigger_word and (not tags or tags[0] != self.trigger_word):
            tags.insert(0, self.trigger_word)
        return ", ".join(tags) + (". " + s.caption if s.caption and s.caption not in tags else "")

    # ------------------------------------------------------------------
    def __getitem__(self, idx: int) -> dict:
        s = self.samples[idx]
        with Image.open(s.image_path) as im:
            im = im.convert("RGB")
            tw, th = s.bucket
            iw, ih = im.size
            scale = max(tw / iw, th / ih)
            nw, nh = int(round(iw * scale)), int(round(ih * scale))
            im = im.resize((nw, nh), Image.LANCZOS)
            cl = (nw - tw) // 2
            ct = (nh - th) // 2
            im = im.crop((cl, ct, cl + tw, ct + th))
            crop_tl = (ct, cl)         # (top, left) for SDXL paper convention

        x = TF.to_tensor(im)           # CHW [0,1]

        # BaSiC photometric normalisation
        if self.basic is not None and random.random() < self.apply_basic_prob:
            import numpy as np
            import cv2
            img_bgr = cv2.cvtColor(
                (x.permute(1, 2, 0).numpy() * 255).astype("uint8"),
                cv2.COLOR_RGB2BGR,
            )
            corrected = self.basic.apply_correction(img_bgr)
            x = TF.to_tensor(
                Image.fromarray(cv2.cvtColor(corrected, cv2.COLOR_BGR2RGB))
            )

        # Compute foreground mask for augmentations
        fg_mask = None
        if self.birefnet is not None:
            try:
                fg_mask = self.birefnet.get_soft_mask(im)  # (H,W) float32 [0,1]
                if not isinstance(fg_mask, torch.Tensor):
                    import numpy as np
                    fg_mask = torch.from_numpy(np.array(fg_mask, dtype="float32"))
                fg_mask = fg_mask.unsqueeze(0)             # (1,H,W)
            except Exception:
                fg_mask = None

        # [-1, 1] conversion before augmentations
        x = x * 2.0 - 1.0
        for aug in self.augmentations:
            x = aug(x, mask=fg_mask)

        caption = self._build_caption(s)

        # Tokenise for CLIP-L
        ids1 = self.tok1(
            caption,
            padding="max_length",
            max_length=self.tok1.model_max_length,
            truncation=True,
            return_tensors="pt",
        ).input_ids[0]

        result = {
            "pixel_values": x,
            "input_ids_one": ids1,
            "original_size": torch.tensor(list(s.original_size), dtype=torch.long),
            "target_size": torch.tensor(list(s.bucket), dtype=torch.long),
            "crop_top_left": torch.tensor(list(crop_tl), dtype=torch.long),
        }

        # Second tokeniser (SDXL / OpenCLIP-bigG)
        if self.tok2 is not None:
            ids2 = self.tok2(
                caption,
                padding="max_length",
                max_length=self.tok2.model_max_length,
                truncation=True,
                return_tensors="pt",
            ).input_ids[0]
            result["input_ids_two"] = ids2

        return result
