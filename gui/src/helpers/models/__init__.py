"""Model helpers and background training workers.

Uses lazy attribute loading (PEP 562) to prevent heavy ML packages (diffusers,
peft, accelerate) from loading at application startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .lora_training_worker import LoRATrainingWorker
    from .tag_review_worker import TagReviewWorker
    from .training_worker import TrainingWorker


def __getattr__(name: str):
    if name == "LoRATrainingWorker":
        from .lora_training_worker import LoRATrainingWorker

        return LoRATrainingWorker
    if name == "TagReviewWorker":
        from .tag_review_worker import TagReviewWorker

        return TagReviewWorker
    if name == "TrainingWorker":
        from .training_worker import TrainingWorker

        return TrainingWorker
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["LoRATrainingWorker", "TagReviewWorker", "TrainingWorker"]
