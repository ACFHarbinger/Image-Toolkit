"""
QThread worker for content recommendations via the local Recommendation Engine.

Uses BGE-M3 hybrid search (dense cosine + sparse dot-product, RRF fusion)
backed by a SQLite store at IMAGE_TOOLKIT_DIR/rec_engine.db.
No external services or C++ extensions required.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

# Absolute path to the standalone Recommendation-Engine package
_RE_DIR = Path(__file__).resolve().parents[4] / "Recommendation-Engine"


def _ensure_re_on_path() -> None:
    """Add Recommendation-Engine/ to sys.path so ``from src.X import Y`` works."""
    path = str(_RE_DIR)
    if path not in sys.path:
        sys.path.insert(0, path)


class RecommendationWorker(QThread):
    """
    Generates recommendations using the local Recommendation Engine.

    Workflow
    --------
    1. Sync *entries* → SQLite store (only newly added entries are embedded).
    2. Build a ParsedQuery from the structured *inputs* dict.
    3. Run HybridRetriever + Scorer to produce a ranked result list.
    4. Emit ``finished`` with ``List[Tuple[str, float]]`` (UUID, score).

    Parameters
    ----------
    entries      : Already-loaded content-listing dicts from the secure DB.
    all_entities : Entity records with at least ``id`` and ``name`` keys,
                   used to resolve entity UUIDs → names for sparse embedding.
    inputs       : Dict from RecommendationDialog.get_inputs(); keys:
                     prompt   – Natural language description.
                     type     – Listing type filter ("All Types" to skip).
                     genres   – Comma-separated genres.
                     tags     – Comma-separated tags.
                     entities – Comma-separated entity names.
    top_k        : Maximum number of results to return (default 50).
    """

    finished = Signal(list)    # List[Tuple[str, float]]
    error = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)  # current, total

    def __init__(
        self,
        entries: List[Dict[str, Any]],
        all_entities: List[Dict[str, Any]],
        inputs: Dict[str, Any],
        top_k: int = 50,
        parent=None,
    ):
        super().__init__(parent)
        self._entries = list(entries)
        self._all_entities = list(all_entities)
        self._inputs = inputs
        self._top_k = top_k

    # ------------------------------------------------------------------
    # Entry conversion helpers
    # ------------------------------------------------------------------

    def _entity_name_map(self) -> Dict[str, str]:
        return {e["id"]: e.get("name", "") for e in self._all_entities if e.get("id")}

    def _entry_to_payload(
        self, entry: Dict[str, Any], name_map: Dict[str, str]
    ) -> Optional[Dict[str, Any]]:
        """
        Convert a listings-tab entry dict to a MediaItem-compatible dict.

        Resolves associated_entities UUID list → human-readable names so that
        the sparse embedding captures meaningful lexical signal.
        """
        eid = (entry.get("id") or "").strip()
        title = (entry.get("title") or "").strip()
        if not eid or not title:
            return None

        raw_rating = entry.get("personal_rating") or entry.get("rating") or 0
        rating = float(raw_rating) if float(raw_rating) > 0 else None

        year = entry.get("year") or 0
        year = None if not year or year == 0 else int(year)

        episodes = entry.get("episodes") or 0
        episodes = None if not episodes or episodes == 0 else int(episodes)

        # Resolve entity IDs → names
        raw_ents = entry.get("associated_entities") or []
        entity_names = [name_map[uid] for uid in raw_ents if name_map.get(uid)]

        # Use review as primary dense text; fall back to summary
        review_text = (entry.get("review") or "").strip() or (entry.get("summary") or "").strip()

        return {
            "id": eid,
            "title": title,
            "type": entry.get("type", ""),
            "status": entry.get("status", ""),
            "rating": rating,
            "year": year,
            "episodes": episodes,
            "genres": entry.get("genres", ""),
            "tags": entry.get("tags", ""),
            "associated_entities": entity_names,
            "local_file": entry.get("local_file", ""),
            "web_link": entry.get("web_link", ""),
            "review": review_text or None,
        }

    # ------------------------------------------------------------------
    # Query construction
    # ------------------------------------------------------------------

    def _build_query(self):
        """
        Return (semantic_query, filter_clauses) from dialog inputs.

        Genres, tags, and entity names are folded into the semantic query so
        the sparse leg can match them via lexical similarity.  Only the type
        field is turned into a hard SQL filter.
        """
        prompt = (self._inputs.get("prompt") or "").strip()
        type_val = (self._inputs.get("type") or "").strip()
        genres_text = (self._inputs.get("genres") or "").strip()
        tags_text = (self._inputs.get("tags") or "").strip()
        entities_text = (self._inputs.get("entities") or "").strip()

        kw_parts: List[str] = []
        if genres_text:
            kw_parts.append(f"Genres: {genres_text}")
        if tags_text:
            kw_parts.append(f"Tags: {tags_text}")
        if entities_text:
            kw_parts.append(f"Featuring: {entities_text}")
        keyword_text = ". ".join(kw_parts)

        if prompt and keyword_text:
            semantic_query = f"{prompt}. {keyword_text}"
        elif prompt:
            semantic_query = prompt
        else:
            semantic_query = keyword_text

        filter_clauses = []
        if type_val and type_val not in ("All Types", "All", ""):
            from src.schema import FilterClause  # pyrefly: ignore [missing-import]
            filter_clauses.append(FilterClause(field="type", op="eq", value=type_val))

        return semantic_query, filter_clauses

    # ------------------------------------------------------------------
    # Main thread body
    # ------------------------------------------------------------------

    def run(self) -> None:
        try:
            _ensure_re_on_path()

            from backend.src.constants import IMAGE_TOOLKIT_DIR

            from src.config import Settings  # pyrefly: ignore [missing-import]
            from src.embedder import Embedder  # pyrefly: ignore [missing-import]
            from src.query_parser import _build_sql_filter  # pyrefly: ignore [missing-import]
            from src.retriever import HybridRetriever  # pyrefly: ignore [missing-import]
            from src.schema import HistoryProfile, MediaItem, ParsedQuery  # pyrefly: ignore [missing-import]
            from src.scorer import Scorer  # pyrefly: ignore [missing-import]
            from src.store import SQLiteStore  # pyrefly: ignore [missing-import]

            # ---- Store setup ----
            db_path = str(IMAGE_TOOLKIT_DIR / "rec_engine.db")
            settings = Settings(sqlite_path=db_path)
            store = SQLiteStore(settings)
            store.create_collection()

            # ---- Incremental sync: embed only new entries ----
            existing_ids = {row["id"] for row in store.fetch_filtered()}
            name_map = self._entity_name_map()

            new_payloads: List[Dict[str, Any]] = []
            for entry in self._entries:
                if entry.get("id") in existing_ids:
                    continue
                payload = self._entry_to_payload(entry, name_map)
                if payload is not None:
                    new_payloads.append(payload)

            embedder = Embedder(settings.embed_model)

            if new_payloads:
                self.status.emit(
                    f"Loading embedding model and indexing {len(new_payloads)} new items…"
                )
                self.progress.emit(0, len(new_payloads))

                items_to_embed: List[MediaItem] = []
                for p in new_payloads:
                    try:
                        items_to_embed.append(MediaItem.model_validate(p))
                    except Exception as exc:
                        logger.debug("Skipping entry %s: %s", p.get("id"), exc)

                def _cb(cur: int, tot: int) -> None:
                    self.progress.emit(cur, tot)
                    self.status.emit(f"Indexing… {cur}/{tot}")

                embedded = embedder.embed_batch(
                    items_to_embed, batch_size=16, progress_callback=_cb
                )
                store.upsert(embedded)
                self.status.emit(f"Indexed {len(embedded)} new items.")
            else:
                self.status.emit("Index is up-to-date. Searching…")

            total_indexed = store.collection_info()["points_count"]
            if total_indexed == 0:
                self.error.emit(
                    "No items in the recommendation index yet. "
                    "Add some listings first."
                )
                return

            # ---- Build query ----
            semantic_query, filter_clauses = self._build_query()
            if not semantic_query:
                self.error.emit(
                    "Please enter a natural language prompt or at least one "
                    "keyword field (genres, tags, or entities)."
                )
                return

            self.status.emit("Searching…")
            sql_filter = _build_sql_filter(filter_clauses)
            parsed = ParsedQuery(semantic_query=semantic_query, filters=filter_clauses)

            # ---- Retrieve ----
            retriever = HybridRetriever(store, embedder, settings)
            candidates = retriever.retrieve(
                parsed, top_k=self._top_k * 2, sql_filter=sql_filter
            )

            # ---- Watch-history boost from completed / highly-rated entries ----
            history: Optional[HistoryProfile] = None
            try:
                profile_payloads = []
                for e in self._entries:
                    raw_rating = e.get("personal_rating") or e.get("rating") or 0
                    if (
                        e.get("status") in ("Completed", "Watching / Reading")
                        and float(raw_rating) >= settings.history_min_rating
                    ):
                        genres_raw = e.get("genres", "") or ""
                        tags_raw = e.get("tags", "") or ""
                        profile_payloads.append({
                            "genres": [g.strip() for g in genres_raw.split(",") if g.strip()],
                            "tags": [t.strip() for t in tags_raw.split(",") if t.strip()],
                        })
                if profile_payloads:
                    history = HistoryProfile.from_payloads(profile_payloads)
            except Exception:
                pass  # history boost is best-effort

            # ---- Score + rank ----
            scorer = Scorer(settings)
            ranked = scorer.score(candidates, parsed, history)[: self._top_k]

            results = [(r.item.id, r.recommendation_value) for r in ranked]
            self.status.emit(f"Done — {len(results)} recommendation(s) found.")
            self.progress.emit(1, 1)
            self.finished.emit(results)

        except Exception as exc:
            logger.exception("[RecommendationWorker] %s", exc)
            self.error.emit(str(exc))
