"""Kind-specific constants for the shared listings subtab package (#563)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ListingsProfile:
    kind: Literal["entity", "series"]
    enc_filename: str
    sync_worker_label: str
    item_noun: str
    sync_success_noun: str
    backup_doc_label: str


ENTITY_PROFILE = ListingsProfile(
    kind="entity",
    enc_filename="entities.json.enc",
    sync_worker_label="Entity",
    item_noun="entities",
    sync_success_noun="entities",
    backup_doc_label="entities backup",
)

SERIES_PROFILE = ListingsProfile(
    kind="series",
    enc_filename="listings.json.enc",
    sync_worker_label="Content",
    item_noun="listings",
    sync_success_noun="listings",
    backup_doc_label="listings backup",
)


__all__ = ["ListingsProfile", "ENTITY_PROFILE", "SERIES_PROFILE"]
