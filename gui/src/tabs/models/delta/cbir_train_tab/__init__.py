"""Training tab for the CBIR (Reverse Image Search) embedding model.

Plugs into :class:`~gui.src.tabs.models.train_tab.UnifiedTrainTab` as a
fourth option alongside LoRA, R3GAN, and AnimeStitchNet.

Architecture overview
---------------------
* Dataset group  — image directory, output directory, val split.
* Backbone group — CLIP ViT-B/32 / ResNet-50 / EfficientNet-V2-S, projection
                   head width and depth, freeze-backbone warm-up epochs.
* Loss group     — InfoNCE (NT-Xent) or TripletMargin; temperature / margin.
* Training group — epochs, batch size, learning rate, warmup, AMP, workers.
* Logging group  — TensorBoard run name, optional W&B toggle.
* FAISS group    — "Build Index" button + image directory / output directory
                   for the post-training index construction step.
* Live telemetry — mini loss chart (unicode sparkline), Recall@1/5/10 display,
                   epoch progress bar, scrollable log box.
"""

from ._sparkline import _SparkLine
from .manager import CBIRTrainTab

__all__ = ["CBIRTrainTab", "_SparkLine"]
