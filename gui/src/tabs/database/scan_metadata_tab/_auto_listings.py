"""DB.8d (scoped): after a Scan & Tag batch upsert touches one or more
image groups, offer to auto-create/link a ``media_items`` listing for any
touched group that has no linked listing yet.

Hooked directly into the live upsert flow (``_upsert_ops.py``'s
``_on_upsert_prepared``) rather than a standalone Management action --
the upsert flow already collects each entry's ``group_name`` and commits
in one transaction, so "which groups were just touched" is a one-line
collection, not new plumbing.

Series/episode detection from directory scans (the original roadmap
text) is NOT attempted here -- out of scope, heuristic-heavy. This only
proposes one ``media_items`` row per newly-populated *image group* with
no existing link, exactly mirroring DB.8a's own "propose, then a human
confirms, then one transaction" pattern (see
``MediaRepo.suggest_group_matches()``'s docstring).
"""

from __future__ import annotations

from typing import Dict, List

from backend.src.database.unified.image_repo import ImageRepo
from backend.src.database.unified.media_repo import MediaRepo
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gui.src.constants.elements import _WORD_RE
from gui.src.helpers.database.library_session import get_library_db


def _words(text: str) -> set:
    return set(_WORD_RE.findall(text.lower()))


def _shares_whole_word(a: str, b: str) -> bool:
    """True if *a* and *b* share at least one whole word -- the "well
    enough" fuzzy-match gate: a plain substring hit (e.g. "Ai" inside
    "Aikatsu") is noisy, a shared whole word is a much stronger signal."""
    return bool(_words(a) & _words(b))


class _AutoListingsMixin:
    """Trigger + review dialog for auto-creating/linking listings from
    newly-populated image groups."""

    def _maybe_offer_auto_listings(self, touched_group_names: List[str]) -> None:
        if not touched_group_names:
            return

        vault_manager = getattr(self.db_tab_ref, "vault_manager", None)
        raw_db = get_library_db(vault_manager, parent=self)
        if raw_db is None:
            return  # vault locked or session unavailable -- silently skip

        image_repo = ImageRepo(raw_db)
        media_repo = MediaRepo(raw_db)
        id_by_title: Dict[str, str] = {}
        for media_id, title in media_repo.list_ids_and_titles():
            id_by_title.setdefault(title, media_id)  # first id wins on duplicate titles
        all_titles = list(id_by_title)

        candidates: List[Dict] = []
        seen_group_ids = set()
        for group_name in touched_group_names:
            if not group_name or not group_name.strip():
                continue
            group_id = image_repo.add_group(group_name)  # idempotent get-or-create
            if group_id in seen_group_ids:
                continue
            seen_group_ids.add(group_id)

            if media_repo.get_media_for_group(group_id):
                continue  # already linked to a listing -- nothing to propose

            suggestions = media_repo.suggest_group_matches(group_name, all_titles)
            best_match = next(
                (t for t in suggestions if _shares_whole_word(group_name, t)), None
            )
            candidates.append({
                "group_id": group_id,
                "group_name": group_name,
                "suggested_title": best_match,
                "suggested_media_id": id_by_title.get(best_match) if best_match else None,
            })

        if not candidates:
            return

        dialog = _AutoListingsReviewDialog(candidates, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        decisions = dialog.decisions()
        if not decisions:
            return

        try:
            raw_db.begin()
            for decision in decisions:
                if decision["action"] == "existing":
                    media_repo.link_group(decision["media_id"], decision["group_id"])
                else:
                    new_id = media_repo.save_media({"title": decision["title"]})
                    media_repo.link_group(new_id, decision["group_id"])
            raw_db.commit()
        except Exception:
            raw_db.rollback()
            raise


class _AutoListingsReviewDialog(QDialog):
    """One batched review dialog: a checkable, editable table of candidate
    image groups with no linked listing yet."""

    def __init__(self, candidates: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Suggested Listings for New Image Groups")
        self.resize(640, 320)
        self._candidates = candidates

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "These newly-scanned image groups have no linked listing yet. "
            "Review and confirm below (unchecked rows are skipped)."
        ))

        self.table = QTableWidget(len(candidates), 4)
        self.table.setHorizontalHeaderLabels(
            ["Include", "Image Group", "Action", "Title"]
        )
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch
        )

        for row, cand in enumerate(candidates):
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            check_item.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(row, 0, check_item)

            group_item = QTableWidgetItem(cand["group_name"])
            group_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row, 1, group_item)

            action_combo = QComboBox()
            action_combo.addItem("Create new listing", userData="new")
            if cand["suggested_title"]:
                action_combo.addItem(
                    f"Link to existing: {cand['suggested_title']}", userData="existing"
                )
                action_combo.setCurrentIndex(1)  # default to the confirmed suggestion
            self.table.setCellWidget(row, 2, action_combo)

            title_edit = QLineEdit(cand["group_name"])
            title_edit.setEnabled(action_combo.currentData() != "existing")
            action_combo.currentIndexChanged.connect(
                lambda _idx, combo=action_combo, edit=title_edit: edit.setEnabled(
                    combo.currentData() != "existing"
                )
            )
            self.table.setCellWidget(row, 3, title_edit)

        layout.addWidget(self.table)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def decisions(self) -> List[Dict]:
        """[{"action": "new"|"existing", "group_id", "title"?, "media_id"?}, ...]
        for every checked row."""
        out: List[Dict] = []
        for row, cand in enumerate(self._candidates):
            check_item = self.table.item(row, 0)
            if check_item is None or check_item.checkState() != Qt.CheckState.Checked:
                continue
            action_combo: QComboBox = self.table.cellWidget(row, 2)  # type: ignore[assignment]
            title_edit: QLineEdit = self.table.cellWidget(row, 3)  # type: ignore[assignment]
            action = action_combo.currentData()
            if action == "existing":
                out.append({
                    "action": "existing",
                    "group_id": cand["group_id"],
                    "media_id": cand["suggested_media_id"],
                    "title": cand["suggested_title"],
                })
            else:
                title = title_edit.text().strip() or cand["group_name"]
                out.append({
                    "action": "new",
                    "group_id": cand["group_id"],
                    "title": title,
                })
        return out


__all__ = ["_AutoListingsMixin"]
