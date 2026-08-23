"""
backend/src/models/data/captioner.py
=====================================
Hybrid anime captioning: WD14 (booru tags) + Florence-2 (natural language).

The HybridCaptioner produces a combined caption:
    "<trigger>, <character_tags>, <always_first_tags>, <general_tags>. <nl_sentence>"

This format is optimal for:
  - Illustrious XL / NoobAI XL: tags + optional prose
  - FLUX / MM-DiT: the nl_caption field can be used standalone
  - Pony V6: prepend score tags before using final_caption

``caption_mode`` selects between the two output shapes (content_generation.md
§1.1): ``"booru"`` (default) produces the tag string above; ``"prose"`` skips
WD14 entirely and returns a pure Florence-2 sentence (with the trigger token
still prefixed, if one is configured) — kept for callers that want plain
natural-language captions rather than booru tags.

WD14 backend
------------
Two interchangeable WD14 backends are accepted as ``wd=``:

  - ``WD14Tagger`` (this module) — loads a local ``.onnx`` + ``selected_tags.csv``
    pair directly, no download step. Used by ``anime_training_pipeline.py``
    when an explicit local model path is configured.
  - ``WDTaggerWrapper`` (``backend/src/models/wrappers/wd_tagger_wrapper.py``,
    §4.4 Auto-Tagger) — the shared tagger wrapper: auto-downloads weights from
    Hugging Face Hub and is the same class any future tag-review-queue UI
    would use. This is the recommended default since it needs no local model
    path and shares improvements with the auto-tagger feature. It reads the
    image from disk itself, so pass ``image_path=`` to ``HybridCaptioner()``
    when using it.

Usage
-----
    # Local ONNX path (legacy / explicit):
    wd = WD14Tagger(onnx_path="wd-eva02-large-tagger-v3.onnx", tags_csv="selected_tags.csv")

    # Or the shared auto-downloading wrapper (recommended):
    from backend.src.models.wrappers.wd_tagger_wrapper import WDTaggerWrapper
    wd = WDTaggerWrapper()

    fl = Florence2Captioner()
    captioner = HybridCaptioner(wd=wd, florence=fl, trigger="my_char_xyz")
    result = captioner(image, image_path="image.png")  # image_path needed for WDTaggerWrapper
    # result["final_caption"] → ready to write to .txt file
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Optional, Union

import numpy as np
from PIL import Image

from backend.src.constants.models import _DEFAULT_UNDESIRED
from backend.src.models.wrappers.wd_tagger_wrapper import WDTaggerWrapper

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy imports
# ---------------------------------------------------------------------------
try:
    import onnxruntime as ort
    _ORT_OK = True
except ImportError:
    _ORT_OK = False
    log.warning("onnxruntime not installed — WD14Tagger unavailable")

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoProcessor
    _TRANSFORMERS_OK = True
except ImportError:
    _TRANSFORMERS_OK = False
    log.warning("transformers not installed — Florence2Captioner unavailable")

# ---------------------------------------------------------------------------
# WD-EVA02 tagger
# ---------------------------------------------------------------------------
class WD14Tagger:
    """
    Wraps SmilingWolf wd-eva02-large-tagger-v3 (or any WD14-compatible ONNX model).

    Parameters
    ----------
    onnx_path        : path to the .onnx model file
    tags_csv         : path to selected_tags.csv (columns: name, category)
    device           : 'cuda' or 'cpu'
    general_thresh   : confidence threshold for general tags
    character_thresh : confidence threshold for character tags (higher = fewer FP)
    """

    def __init__(
        self,
        onnx_path: str,
        tags_csv: str,
        device: str = "cuda",
        general_thresh: float = 0.35,
        character_thresh: float = 0.85,
    ):
        if not _ORT_OK:
            raise ImportError("onnxruntime is required for WD14Tagger")

        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if device == "cuda"
            else ["CPUExecutionProvider"]
        )
        self.sess = ort.InferenceSession(onnx_path, providers=providers)
        self.input_name = self.sess.get_inputs()[0].name

        with open(tags_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.tag_names = [r["name"] for r in rows]
        self.tag_categories = [int(r["category"]) for r in rows]
        self.general_thresh = general_thresh
        self.character_thresh = character_thresh

    def __call__(
        self, image: Image.Image
    ) -> tuple[list[str], list[str], list[str]]:
        """
        Returns (rating_tags, general_tags, character_tags).
        Category codes: 9=rating, 0=general, 4=character.
        """
        img = image.convert("RGB").resize((448, 448), Image.BICUBIC)
        arr = np.array(img, dtype=np.float32)[..., ::-1]  # RGB → BGR
        arr = np.expand_dims(arr, 0)
        probs = self.sess.run(None, {self.input_name: arr})[0][0]

        rating, general, character = [], [], []
        for name, cat, p in zip(self.tag_names, self.tag_categories, probs, strict=False):
            name_clean = name.replace("_", " ")
            if cat == 9 and p > 0.5:
                rating.append(name_clean)
            elif cat == 0 and p > self.general_thresh:
                general.append(name_clean)
            elif cat == 4 and p > self.character_thresh:
                character.append(name_clean)
        return rating, general, character

# ---------------------------------------------------------------------------
# Florence-2 natural-language captioner
# ---------------------------------------------------------------------------
class Florence2Captioner:
    """
    Wraps microsoft/Florence-2-large-ft (or PromptGen v1.5/v2.0 fine-tunes).

    For LoRA training on < 200 images, prefer WD14 tags only.
    Mix in Florence-2 when the dataset exceeds ~500 images.
    """

    def __init__(
        self,
        repo: str = "microsoft/Florence-2-large-ft",
        device: str = "cuda",
        dtype=None,
    ):
        if not _TRANSFORMERS_OK:
            raise ImportError("transformers is required for Florence2Captioner")
        dtype = dtype or (torch.float16 if device == "cuda" else torch.float32)
        self.proc = AutoProcessor.from_pretrained(repo, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            repo,
            trust_remote_code=True,
            dtype=dtype,
            attn_implementation="eager"
        ).to(device).eval()
        self.device = device
        self.dtype = dtype

    @property
    def _torch(self):
        return torch

    def __call__(
        self,
        image: Image.Image,
        task: str = "<MORE_DETAILED_CAPTION>",
    ) -> str:
        inputs = self.proc(
            text=task, images=image.convert("RGB"), return_tensors="pt"
        ).to(self.device, self.dtype)
        with self._torch.inference_mode():
            ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=256,
                num_beams=3,
                do_sample=False,
                use_cache=False,
            )
        text = self.proc.batch_decode(ids, skip_special_tokens=False)[0]
        return self.proc.post_process_generation(
            text, task=task, image_size=image.size
        )[task]

# ---------------------------------------------------------------------------
# WD14 backend adapter — normalizes WD14Tagger and WDTaggerWrapper to one shape
# ---------------------------------------------------------------------------
def _wd_tag(
    wd: "Union[WD14Tagger, WDTaggerWrapper]",
    image: Image.Image,
    image_path: Optional[Union[str, Path]] = None,
) -> tuple[list[str], list[str], list[str]]:
    """
    Run *wd* and normalize its output to ``(rating, general, character)`` tag lists,
    regardless of which of the two supported WD14 backends it is.

    ``WD14Tagger`` operates on a PIL Image directly. ``WDTaggerWrapper`` (the
    shared §4.4 auto-tagger backend) reads the image from disk itself and
    returns ``[{"tag", "confidence", "category"}, ...]``, so *image_path* must
    be supplied when *wd* is a ``WDTaggerWrapper``.
    """
    if isinstance(wd, WD14Tagger):
        return wd(image)

    if image_path is None:
        raise ValueError(
            "image_path is required when the WD14 backend is a WDTaggerWrapper "
            "(it reads the file from disk rather than accepting a PIL Image)."
        )
    tagged = wd.tag(str(image_path))
    rating = [t["tag"] for t in tagged if t["category"] == "rating"]
    character = [t["tag"] for t in tagged if t["category"] == "character"]
    general = [t["tag"] for t in tagged if t["category"] == "general"]
    return rating, general, character


# ---------------------------------------------------------------------------
# Hybrid captioner
# ---------------------------------------------------------------------------

class HybridCaptioner:
    """
    Combines WD14 booru tags with Florence-2 natural language.

    Parameters
    ----------
    wd              : WD14Tagger or WDTaggerWrapper instance (see module docstring)
    florence        : Florence2Captioner instance (may be None for tag-only mode)
    trigger         : unique activation token prepended to every caption
    always_first    : tags always placed at the front (e.g. '1girl')
    undesired       : tags to strip before writing
    model_prefix    : quality/prefix tags prepended for specific base models:
                      'noobai_vpred'  → 'masterpiece, best quality, newest, absurdres, very awa'
                      'illustrious'   → 'masterpiece, best quality, absurdres'
                      'pony'          → 'score_9, score_8_up, score_7_up, source_anime'
                      None / other    → no prefix
    caption_mode    : 'booru' (default) — WD14 tags (+ optional Florence-2 sentence
                      appended). 'prose' — pure Florence-2 sentence only, no WD14
                      tags at all (trigger token is still prefixed, if set).
    """

    MODEL_PREFIXES = {
        "noobai_vpred":  "masterpiece, best quality, newest, absurdres, very awa",
        "illustrious":   "masterpiece, best quality, absurdres",
        "animagine":     "masterpiece, best quality, very aesthetic, absurdres",
        "pony":          "score_9, score_8_up, score_7_up, source_anime",
    }

    def __init__(
        self,
        wd: "Optional[Union[WD14Tagger, WDTaggerWrapper]]",
        florence: Optional[Florence2Captioner],
        trigger: Optional[str] = None,
        always_first: tuple[str, ...] = ("1girl",),
        undesired: frozenset[str] = _DEFAULT_UNDESIRED,
        model_prefix: Optional[str] = None,
        caption_mode: str = "booru",
    ):
        if caption_mode not in ("booru", "prose"):
            raise ValueError(
                f"caption_mode must be 'booru' or 'prose', got {caption_mode!r}"
            )
        self.wd = wd
        self.fl = florence
        self.trigger = trigger
        self.always_first = always_first
        self.undesired = undesired
        self.prefix = self.MODEL_PREFIXES.get(model_prefix or "", "")
        self.caption_mode = caption_mode

    def __call__(
        self,
        image: Image.Image,
        image_path: Optional[Union[str, Path]] = None,
    ) -> dict:
        """
        Returns dict with keys:
          wd14_rating, wd14_character, wd14_general,
          tags_ordered, nl_caption, final_caption, pruned_tags

        *image_path* is only required when ``wd`` is a ``WDTaggerWrapper``
        (it reads the file from disk rather than accepting a PIL Image).
        """
        if self.caption_mode == "prose":
            if self.fl is None:
                raise RuntimeError(
                    "HybridCaptioner(caption_mode='prose') requires a "
                    "Florence2Captioner instance (florence=...); none was provided."
                )
            nl = self.fl(image)
            final = f"{self.trigger}, {nl}" if self.trigger else nl
            return {
                "wd14_rating": [],
                "wd14_character": [],
                "wd14_general": [],
                "tags_ordered": [],
                "nl_caption": nl,
                "final_caption": final,
                "pruned_tags": [],
            }

        if self.wd is not None:
            rating, general, character = _wd_tag(self.wd, image, image_path)
            general = [t for t in general if t not in self.undesired]
        else:
            rating, general, character = [], [], []

        # Build ordered tag list: character → always_first → general
        ordered: list[str] = []
        for t in character:
            if t not in ordered:
                ordered.append(t)
        for t in self.always_first:
            if t not in ordered:
                ordered.append(t)
        for t in general:
            if t not in ordered:
                ordered.append(t)

        if self.trigger and self.trigger not in ordered:
            ordered = [self.trigger] + ordered

        tag_str = self.prefix + ", " + ", ".join(ordered) if self.prefix else ", ".join(ordered)

        nl = self.fl(image) if self.fl is not None else ""
        final = (tag_str + ". " + nl).strip(". ") if nl else tag_str

        return {
            "wd14_rating": rating,
            "wd14_character": character,
            "wd14_general": general,
            "tags_ordered": ordered,
            "nl_caption": nl,
            "final_caption": final,
            "pruned_tags": ordered,
        }

    def write_caption_file(self, image_path: Path, caption_dict: dict) -> None:
        """Write final_caption to a .txt sidecar file alongside the image."""
        txt_path = image_path.with_suffix(".txt")
        txt_path.write_text(caption_dict["final_caption"], encoding="utf-8")
