"""Atomic local persistence for versioned learning catalogs."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .model import LearningCatalog


def save_catalog(path: str | Path, catalog: LearningCatalog) -> Path:
    """Atomically save teaching content/settings without network access."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=destination.parent, delete=False) as handle:
        json.dump(catalog.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def load_catalog(path: str | Path) -> LearningCatalog:
    """Load, migrate, and validate a local learning catalog."""
    return LearningCatalog.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
