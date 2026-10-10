"""Vocabulary providers backing PromptEdit's autocomplete and chips (#733).

Everything PromptEdit needs is data the app already owns: the library's
tag corpus (ranked by real usage), the WD14 tagger's canonical tag list,
and — once Gate D (#741) starts writing run records — trigger words and
train-time negatives from past runs. Providers are plain objects so the
GUI can fetch from them off the GUI thread and tests need no database.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TagSuggestion:
    tag: str
    category: str = ""
    uses: int = 0


class VocabularyProvider(Protocol):
    """Autocomplete + chips data source for PromptEdit."""

    def suggest(self, prefix: str, limit: int = 12) -> list[TagSuggestion]: ...

    def trigger_tokens(self) -> list[str]: ...

    def negative_for_lora(self, lora_path: str) -> str | None: ...


class NullVocabulary:
    """No-data default; the component degrades to a plain editor."""

    def suggest(self, prefix: str, limit: int = 12) -> list[TagSuggestion]:
        return []

    def trigger_tokens(self) -> list[str]:
        return []

    def negative_for_lora(self, lora_path: str) -> str | None:
        return None


class StaticVocabulary:
    """Fixed tag list — tests and offline safety net."""

    def __init__(self, tags: tuple[str, ...] = ()):
        self._tags = tuple(TagSuggestion(t) for t in tags)

    def suggest(self, prefix: str, limit: int = 12) -> list[TagSuggestion]:
        p = prefix.lower()
        return [s for s in self._tags if s.tag.startswith(p)][:limit]

    def trigger_tokens(self) -> list[str]:
        return []

    def negative_for_lora(self, lora_path: str) -> str | None:
        return None


class CompositeVocabulary:
    """First-hit-wins merge; dedupes suggestions by tag."""

    def __init__(self, providers: list[VocabularyProvider]):
        self._providers = list(providers)

    def suggest(self, prefix: str, limit: int = 12) -> list[TagSuggestion]:
        seen: set[str] = set()
        out: list[TagSuggestion] = []
        for provider in self._providers:
            for suggestion in provider.suggest(prefix, limit):
                if suggestion.tag in seen:
                    continue
                seen.add(suggestion.tag)
                out.append(suggestion)
                if len(out) >= limit:
                    return out
        return out

    def trigger_tokens(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for provider in self._providers:
            for token in provider.trigger_tokens():
                if token not in seen:
                    seen.add(token)
                    out.append(token)
        return out

    def negative_for_lora(self, lora_path: str) -> str | None:
        for provider in self._providers:
            negative = provider.negative_for_lora(lora_path)
            if negative:
                return negative
        return None


class DbVocabulary:
    """Library tag corpus ranked by image_tags usage frequency.

    rows_factory must return (tag, category, uses) tuples; it is injected
    so tests need no database and the GUI resolves the unified facade
    lazily (never at tab-construction time).
    """

    def __init__(self, rows_factory: Callable[[], list[tuple[str, str, int]]] | None = None):
        self._rows_factory = rows_factory or _default_tag_rows

    def suggest(self, prefix: str, limit: int = 12) -> list[TagSuggestion]:
        p = prefix.lower()
        try:
            rows = self._rows_factory()
        except Exception as exc:  # DB unavailable — autocomplete just stays empty
            logger.info("tag vocabulary unavailable: %s", exc)
            return []
        ranked = sorted(rows, key=lambda r: r[2], reverse=True)
        return [
            TagSuggestion(tag, category, uses)
            for tag, category, uses in ranked
            if tag.lower().startswith(p)
        ][:limit]

    def trigger_tokens(self) -> list[str]:
        return []

    def negative_for_lora(self, lora_path: str) -> str | None:
        return None


def _default_tag_rows() -> list[tuple[str, str, int]]:
    from backend.src.database.unified import session
    from backend.src.database.unified.facade import UnifiedImageDatabase

    db = UnifiedImageDatabase(session.get_session())
    return db.tag_repo.popular_tags_with_uses()


def model_prefix_for(model_id: str) -> str | None:
    """HybridCaptioner.MODEL_PREFIXES entry whose key folds into model_id.

    'OnomaAIResearch/Illustrious-XL-v2.0' -> 'masterpiece, best quality,
    absurdres'. Imported lazily — the captioner chain is backend-heavy.
    """
    try:
        from backend.src.models.data.captioner import HybridCaptioner
    except Exception as exc:
        logger.info("captioner prefixes unavailable: %s", exc)
        return None
    folded = "".join(ch for ch in model_id.lower() if ch.isalnum())
    for key, prefix in HybridCaptioner.MODEL_PREFIXES.items():
        if key.lower() in folded:
            return prefix
    return None


def default_vocabulary(run_dirs: tuple[str, ...] = ()) -> VocabularyProvider:
    """Production PromptEdit wiring (#733): library corpus first (ranked by
    real usage), WD14 canonical list as fallback, run records for trigger
    chips + train-time negatives once Gate D defines the store."""
    return CompositeVocabulary(
        [DbVocabulary(), Wd14FallbackVocabulary(), RunRecordStore(run_dirs)]
    )


class Wd14FallbackVocabulary:
    """Canonical WD14 tag list from the tagger's selected_tags.csv.

    Loaded lazily from the Hugging Face cache — the CSV only, no ONNX
    model. Empty when the file cannot be fetched.
    """

    _CSV_REPO = "SmilingWolf/wd-v1-4-convnext-tagger-v2"
    _CSV_NAME = "selected_tags.csv"

    def __init__(self) -> None:
        self._tags: list[TagSuggestion] | None = None

    def _load(self) -> list[TagSuggestion]:
        if self._tags is None:
            try:
                from huggingface_hub import hf_hub_download

                path = hf_hub_download(repo_id=self._CSV_REPO, filename=self._CSV_NAME)
                with open(path, newline="", encoding="utf-8") as fh:
                    self._tags = [
                        TagSuggestion(row["name"], row.get("category", ""))
                        for row in csv.DictReader(fh)
                        if row.get("name")
                    ]
            except Exception as exc:
                logger.info("WD14 fallback vocabulary unavailable: %s", exc)
                self._tags = []
        return self._tags

    def suggest(self, prefix: str, limit: int = 12) -> list[TagSuggestion]:
        p = prefix.lower()
        return [s for s in self._load() if s.tag.startswith(p)][:limit]

    def trigger_tokens(self) -> list[str]:
        return []

    def negative_for_lora(self, lora_path: str) -> str | None:
        return None


class RunRecordStore:
    """Run records as vocabulary: trigger chips + train-time negatives.

    Layout: <base_dir>/<run_id>/record.json with keys trigger_word,
    negative_prompt and lora_path. Gate D (#741) defines the writer; until
    run records exist this yields nothing and the chips rows stay empty.
    base_dirs is a setting, not a hardcoded path, because the runs root is
    itself part of the Gate D record-layout decision.
    """

    def __init__(self, base_dirs: tuple[str, ...] = ()):
        self._dirs = tuple(Path(d) for d in base_dirs)

    def _records(self) -> list[dict]:
        out: list[dict] = []
        for base in self._dirs:
            if not base.is_dir():
                continue
            for path in sorted(base.glob("*/record.json")):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    logger.info("skipping unreadable run record %s: %s", path, exc)
                    continue
                if isinstance(record, dict):
                    out.append(record)
        return out

    def suggest(self, prefix: str, limit: int = 12) -> list[TagSuggestion]:
        return []

    def trigger_tokens(self) -> list[str]:
        tokens: list[str] = []
        for record in self._records():
            token = str(record.get("trigger_word") or "").strip()
            if token and token not in tokens:
                tokens.append(token)
        return tokens

    def negative_for_lora(self, lora_path: str) -> str | None:
        target = (lora_path or "").strip()
        if not target:
            return None
        for record in self._records():
            recorded = str(record.get("lora_path") or "").strip()
            negative = str(record.get("negative_prompt") or "").strip()
            if negative and recorded and (
                recorded == target or recorded.endswith("/" + target) or target.endswith(recorded)
            ):
                return negative
        return None


__all__ = [
    "CompositeVocabulary",
    "DbVocabulary",
    "NullVocabulary",
    "RunRecordStore",
    "StaticVocabulary",
    "TagSuggestion",
    "VocabularyProvider",
    "Wd14FallbackVocabulary",
    "default_vocabulary",
    "model_prefix_for",
]
