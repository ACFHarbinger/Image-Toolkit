"""DB.8c: tag-chip autocomplete for the Genres/Tags fields, drawing from
the unified ``tags`` vocabulary (shared across the image and listings
domains post-migration -- a tag typed on the image side autocompletes
here too, and vice versa).

``TagCompleter`` (``gui/src/helpers/database/tag_completer.py``) already
existed -- built and tested (issue #127) but never actually attached to
any QLineEdit anywhere in the app. This wires it up -- now onto
``TagChipEditor``'s internal add-input (issue #127's real chip-UI half,
``gui/src/components/tag_chip_widget.py``) rather than a plain QLineEdit.
"""

from __future__ import annotations

from backend.src.database.unified.tag_repo import TagRepo
from gui.src.helpers.database.library_session import get_library_db
from gui.src.helpers.database.tag_completer import TagCompleter


class _TagVocabularyMixin:
    """Attach TagCompleter to f_genres/f_tags and keep their vocabulary fresh."""

    def _attach_tag_completers(self) -> None:
        self._genres_completer = TagCompleter()
        self._tags_completer = TagCompleter()
        self.f_genres.attach_completer(self._genres_completer)
        self.f_tags.attach_completer(self._tags_completer)

    def _refresh_tag_vocabulary(self) -> None:
        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            return
        try:
            all_tags = TagRepo(db).get_all_tags()
        except Exception as e:
            print(f"Failed to load tag vocabulary: {e}")
            return
        self._genres_completer.set_tags(all_tags)
        self._tags_completer.set_tags(all_tags)


__all__ = ["_TagVocabularyMixin"]
