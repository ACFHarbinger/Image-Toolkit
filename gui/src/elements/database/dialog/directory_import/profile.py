"""Kind-specific constants for directory-import dialogs (#563)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class DirectoryImportProfile:
    kind: Literal["series", "entity"]
    window_title: str
    directory_group_title: str
    directory_placeholder: str
    browse_dialog_title: str
    status_idle_text: str
    splitter_key: str
    metadata_group_title: str
    existing_key_label: str  # "titles" or "names"
    import_noun: str  # "listings" or "entities"


SERIES_PROFILE = DirectoryImportProfile(
    kind="series",
    window_title="📂 Import Listings from Video Directory",
    directory_group_title="Video Directory",
    directory_placeholder="Select the folder that contains your video files…",
    browse_dialog_title="Select Video Directory",
    status_idle_text="Scan a directory to detect series.",
    splitter_key="directory_import_dialog",
    metadata_group_title="Metadata Applied to All New Entries",
    existing_key_label="titles",
    import_noun="listings",
)

ENTITY_PROFILE = DirectoryImportProfile(
    kind="entity",
    window_title="📂 Import Entities from Image Directory",
    directory_group_title="Image Directory",
    directory_placeholder="Select the folder that contains your entity image files…",
    browse_dialog_title="Select Entity Image Directory",
    status_idle_text="Scan a directory to detect entity images.",
    splitter_key="entity_directory_import_dialog",
    metadata_group_title="Metadata Applied to All New Entities",
    existing_key_label="names",
    import_noun="entities",
)


__all__ = ["DirectoryImportProfile", "SERIES_PROFILE", "ENTITY_PROFILE"]
