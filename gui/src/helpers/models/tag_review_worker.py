from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Signal


class TagReviewWorker(QThread):
    """
    Runs WD14 auto-tagging over a dataset folder off the GUI thread, for the
    human-in-the-loop tag review queue (new_features.md §4.4C).

    Uses ``WDTaggerWrapper.tag_with_review`` (§4.4E, already built but had
    zero callers before this) to split each image's predicted tags into
    *auto* (confidence >= threshold, pre-checked in the review dialog) and
    *review* (borderline confidence, unchecked by default — exactly the
    ones a human should look at). Booru tags only, no Florence-2 sentence:
    the review dialog checks discrete tags, which doesn't map onto a
    natural-language caption.
    """

    sig_progress = Signal(int, int)  # done, total
    # image_path, [(tag, confidence, category, checked_by_default), ...]
    sig_result = Signal(str, list)
    sig_finished = Signal()
    error = Signal(str)

    def __init__(
        self,
        image_paths: List[Path],
        general_thresh: float = 0.35,
        review_thresh: float = 0.15,
        model_repo: Optional[str] = None,
        skip_already_tagged: bool = True,
    ):
        super().__init__()
        self.image_paths = list(image_paths)
        self.general_thresh = general_thresh
        self.review_thresh = review_thresh
        self.model_repo = model_repo
        self.skip_already_tagged = skip_already_tagged

    def run(self):
        try:
            from backend.src.models.wrappers.wd_tagger_wrapper import WDTaggerWrapper

            if not WDTaggerWrapper.is_available():
                self.error.emit(
                    "WD14 tagger unavailable (missing onnxruntime / "
                    "huggingface_hub) — cannot build the review queue."
                )
                return

            wd = WDTaggerWrapper(model_repo=self.model_repo, threshold=self.general_thresh)

            todo = [
                p
                for p in self.image_paths
                if not (self.skip_already_tagged and p.with_suffix(".txt").exists())
            ]
            total = len(todo)
            for i, path in enumerate(todo):
                try:
                    auto, review = wd.tag_with_review(
                        str(path),
                        threshold=self.general_thresh,
                        review_threshold=self.review_thresh,
                    )
                    entries = [
                        (t["tag"], t["confidence"], t["category"], True) for t in auto
                    ] + [
                        (t["tag"], t["confidence"], t["category"], False) for t in review
                    ]
                    self.sig_result.emit(str(path), entries)
                except Exception as exc:
                    self.error.emit(f"Tagging failed for {path.name}: {exc}")
                self.sig_progress.emit(i + 1, total)

            self.sig_finished.emit()
        except Exception as e:
            self.error.emit(f"Tag review worker failed: {e}")
