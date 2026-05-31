"""
Listing ingestion pipeline: JSON → context strings → BGE-M3 vectors → Qdrant.

Usage:
    from backend.src.pipeline.vector_ingestion import ingest_listings
    from backend.src.database.qdrant_manager import QdrantManager

    mgr = QdrantManager("/path/to/qdrant/storage")
    mgr.connect()
    ingest_listings(mgr, "~/.image-toolkit/listings.json", "~/.image-toolkit/entities.json")
"""
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def get_or_load_model():
    """Thread-safe lazy loader for the shared BGE-M3 model singleton."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from FlagEmbedding import BGEM3FlagModel
        except ImportError:
            raise RuntimeError(
                "FlagEmbedding not installed. "
                "Run: pip install 'FlagEmbedding>=1.3.5'"
            )
        t0 = time.perf_counter()
        logger.info(
            "[Ingestion] Loading BAAI/bge-m3 (first load downloads ~2 GB)…"
        )
        _model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
        logger.info("[Ingestion] BGE-M3 loaded in %.1fs", time.perf_counter() - t0)
        return _model


# ------------------------------------------------------------------
# Context String Builder
# ------------------------------------------------------------------

def _build_entity_map(entities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map entity UUID → {name, roles} for fast lookup during ingestion."""
    result: Dict[str, Dict[str, Any]] = {}
    for ent in entities:
        eid = ent.get("id")
        if eid:
            result[eid] = {
                "name": ent.get("name", "Unknown"),
                "roles": ent.get("roles", []),
            }
    return result


def build_context_string(
    entry: Dict[str, Any],
    entity_map: Dict[str, Dict[str, Any]],
) -> str:
    """
    Build a rich text chunk representing a listing's semantic context.

    Format:
        Title: {title}. Type: {type}. Synopsis: {synopsis}.
        Genres: {genres}. Tags: {tags}.
        Featuring: {name} ({role}), …
    """
    parts: List[str] = []

    title = (entry.get("title") or "").strip()
    if title:
        parts.append(f"Title: {title}")

    etype = (entry.get("type") or "").strip()
    if etype:
        parts.append(f"Type: {etype}")

    synopsis = (entry.get("review_notes") or "").strip()
    if synopsis:
        parts.append(f"Synopsis: {synopsis}")

    genres = (entry.get("genres") or "").strip()
    if genres:
        parts.append(f"Genres: {genres}")

    tags = (entry.get("tags") or "").strip()
    if tags:
        parts.append(f"Tags: {tags}")

    entity_strs: List[str] = []
    for eid in entry.get("associated_entities", []):
        if eid in entity_map:
            ent = entity_map[eid]
            name = ent.get("name", "Unknown")
            roles = ent.get("roles", [])
            role_str = ", ".join(roles) if roles else "Unknown"
            entity_strs.append(f"{name} ({role_str})")
    if entity_strs:
        parts.append("Featuring: " + "; ".join(entity_strs))

    return ". ".join(parts) + "."


# ------------------------------------------------------------------
# Ingestion
# ------------------------------------------------------------------

def ingest_listings(
    qdrant_manager,
    listings_path: str,
    entities_path: str,
    batch_size: int = 32,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> int:
    """
    Load listings + entities, embed with BGE-M3, and upsert to Qdrant.

    Args:
        qdrant_manager    : Connected QdrantManager instance.
        listings_path     : Path to listings.json.
        entities_path     : Path to entities.json.
        batch_size        : BGE-M3 encoding batch size (reduce if OOM).
        progress_callback : Optional callable(current, total).

    Returns:
        Number of entries successfully upserted.
    """
    lp = Path(listings_path)
    ep = Path(entities_path)

    entries: List[Dict[str, Any]] = []
    if lp.exists():
        with open(lp, "r", encoding="utf-8") as f:
            entries = json.load(f)
    if not entries:
        logger.warning("[Ingestion] No listings found at %s", lp)
        return 0

    entities: List[Dict[str, Any]] = []
    if ep.exists():
        with open(ep, "r", encoding="utf-8") as f:
            entities = json.load(f)

    entity_map = _build_entity_map(entities)
    logger.info(
        "[Ingestion] Loaded %d listings, %d entities", len(entries), len(entities)
    )

    contexts = [build_context_string(e, entity_map) for e in entries]
    model = get_or_load_model()

    total = len(entries)
    upserted = 0

    for batch_start in range(0, total, batch_size):
        batch_entries = entries[batch_start : batch_start + batch_size]
        batch_contexts = contexts[batch_start : batch_start + batch_size]

        try:
            output = model.encode(
                batch_contexts,
                batch_size=batch_size,
                max_length=512,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
        except Exception as exc:
            logger.error(
                "[Ingestion] Encoding failed for batch %d–%d: %s",
                batch_start,
                batch_start + len(batch_entries),
                exc,
            )
            continue

        dense_vecs = output["dense_vecs"]
        sparse_weights = output["lexical_weights"]

        points: List[Dict[str, Any]] = []
        for i, entry in enumerate(batch_entries):
            listing_id = entry.get("id")
            if not listing_id:
                continue

            dense = dense_vecs[i].tolist()
            sw: Dict[str, float] = sparse_weights[i]
            sp_indices = [int(k) for k in sw.keys()]
            sp_values = [float(v) for v in sw.values()]

            payload = {
                "id": listing_id,
                "title": entry.get("title", ""),
                "type": entry.get("type", ""),
                "watch_status": entry.get("status", ""),
                "year_released": int(entry.get("year_released") or 0),
                "genres": [
                    g.strip()
                    for g in (entry.get("genres") or "").split(",")
                    if g.strip()
                ],
                "tags": [
                    t.strip()
                    for t in (entry.get("tags") or "").split(",")
                    if t.strip()
                ],
                "associated_entities": entry.get("associated_entities", []),
            }

            points.append(
                {
                    "id": listing_id,
                    "dense": dense,
                    "sparse_indices": sp_indices,
                    "sparse_values": sp_values,
                    "payload": payload,
                }
            )

        if points:
            qdrant_manager.upsert_batch(points)
            upserted += len(points)

        if progress_callback:
            progress_callback(batch_start + len(batch_entries), total)

        logger.debug(
            "[Ingestion] %d/%d done (%d upserted)",
            batch_start + len(batch_entries),
            total,
            upserted,
        )

    logger.info(
        "[Ingestion] Complete — %d/%d entries upserted.", upserted, total
    )
    return upserted
