"""Entity Recon and Provenance tab — localized OSINT identity resolution.

A native three-pane QWidget (this app is widget-based, not QML-based):

    Left    source image; click a subject to segment it (SAM 2 → GrabCut
            fallback) or resolve the whole frame
    Center  resolved identity card (name, confidence, method, origin) with
            JSON/CSV provenance export
    Right   provenance trail (local dataset matches or grouped web domains)

Plus a dataset indexer (``/Dataset/FirstName_LastName/image.jpg`` → HNSW
identity index), a Strict Privacy Mode toggle (offline-only), and a batch
dataset builder that auto-sorts dropped images into identity folders.

Heavy work (indexing, segmentation, embedding, resolution) runs in QThread
workers; the C++ ``base.recon`` HNSW index and the torch/SAM models sit behind
graceful fallbacks so the tab stays usable fully offline.
"""

from ._clickable_label import _ClickableImageLabel
from .manager import EntityReconTab

__all__ = ["EntityReconTab", "_ClickableImageLabel"]
