"""Auto-populate controller for groups/subgroups from ``LOCAL_SOURCE_PATH`` (§5.17, #544)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QProgressDialog

if TYPE_CHECKING:
    pass


class DatabaseAutoPopulateController:
    """Scan ``LOCAL_SOURCE_PATH`` to sync groups/subgroups from disk layout."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def auto_populate_from_source(self) -> None:  # noqa: C901
        """
        Scans LOCAL_SOURCE_PATH.
        Level 1 Directories -> Groups
        Level 2 Directories -> Subgroups for that Group
        """
        tab = self.tab
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return

        # Resolve to absolute path to avoid ambiguity
        source_path = Path(LOCAL_SOURCE_PATH).resolve()

        if not source_path.exists():
            QMessageBox.critical(
                tab, "Path Error", f"The source path does not exist:\n{source_path}"
            )
            return

        # Simple confirmation
        confirm = QMessageBox.question(
            tab,
            "Confirm Sync",
            f"This will scan the following directory:\n\n{source_path}\n\n"
            "Top-level folders will be added as Groups.\n"
            "Folders inside those will be added as Subgroups.\n"
            "Existing entries will be skipped.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.No:
            return

        # Progress Dialog
        progress = QProgressDialog("Scanning directories...", "Cancel", 0, 0, tab)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        groups_added = 0
        subgroups_added = 0
        errors = []

        try:
            # Iterate Level 1 (Groups)
            for group_dir in source_path.iterdir():
                if progress.wasCanceled():
                    break

                if group_dir.is_dir() and not group_dir.name.startswith("."):
                    group_name = group_dir.name.strip()
                    if not group_name:
                        continue

                    try:
                        # Add Group to DB (ImageDatabase handles "ON CONFLICT DO NOTHING")
                        tab.db.add_group(group_name)
                        groups_added += 1

                        # Iterate Level 2 (Subgroups)
                        for subgroup_dir in group_dir.iterdir():
                            if (
                                subgroup_dir.is_dir()
                                and not subgroup_dir.name.startswith(".")
                            ):
                                subgroup_name = subgroup_dir.name.strip()
                                if not subgroup_name:
                                    continue

                                try:
                                    # Add Subgroup to DB
                                    tab.db.add_subgroup(subgroup_name, group_name)
                                    subgroups_added += 1
                                except Exception as e_sub:
                                    print(
                                        f"Error adding subgroup {subgroup_name}: {e_sub}"
                                    )
                                    pass

                    except Exception as e_group:
                        errors.append(f"Group '{group_name}': {str(e_group)}")

            progress.close()

            # Refresh UIs
            tab.refresh_groups_list()
            tab._refresh_all_group_combos()
            tab.refresh_subgroup_autocomplete()
            tab.refresh_subgroups_list()
            tab.update_statistics()

            msg = (
                f"Scan Finished.\n\n"
                f"Processed Groups: {groups_added}\n"
                f"Processed Subgroups: {subgroups_added}\n\n"
                f"(Note: Numbers indicate processed folders, duplicates were skipped)."
            )

            if errors:
                msg += "\n\nErrors encountered:\n" + "\n".join(errors[:5])
                if len(errors) > 5:
                    msg += "\n..."

            QMessageBox.information(tab, "Sync Complete", msg)

        except Exception as e:
            progress.close()
            QMessageBox.critical(
                tab, "Sync Error", f"An error occurred during scanning:\n{str(e)}"
            )


# Backward-compatible alias
_AutoPopulateMixin = DatabaseAutoPopulateController

__all__ = ["DatabaseAutoPopulateController", "_AutoPopulateMixin"]
