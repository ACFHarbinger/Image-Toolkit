"""Dataset staging and advisor callbacks for LoRATrainTab."""
import shutil
import sys
from pathlib import Path

from .lora_dataset_staging import (  # noqa: F401
    _DATASET_IMAGE_EXTS,
    _TRAINING_ENGINES,
    ImportedDataset,
    _exclusive_parent,
    _existing_images,
    _image_paths_under,
    _signal_process_group,
    _stage_images,
    _unique_staged_name,
    combine_trigger_and_prompt,
    dataset_folder_from_paths,
    resolve_imported_dataset,
)


class LoRATrainDatasetMixin:
    """LoRATrainTab methods for dataset selection, staging and the advisor."""


    def _apply_resolved(self, imported: ImportedDataset) -> None:
        if self._training_running() or self._review_running():
            if imported.staged and imported.train_dir:
                shutil.rmtree(imported.train_dir, ignore_errors=True)
            self.status_label.setText("Cannot replace the dataset while training is running.")
            return
        if imported.train_dir != self._staging_dir:
            self._clear_staging()
        if imported.staged:
            self._staging_dir = imported.train_dir
        self._dataset_scope = imported.scope
        self._dataset_paths = imported.source_paths
        self._applied_train_dir = imported.train_dir
        self.data_dir_edit.blockSignals(True)
        self.data_dir_edit.setText(imported.train_dir or "")
        self.data_dir_edit.blockSignals(False)
        self.notify_effective_config_changed()
        if imported.train_dir:
            self.last_browsed_scan_dir = imported.train_dir
        count = len(imported.source_paths)
        if imported.scope == "folder":
            self.status_label.setText(f"Dataset folder: {count} image(s)")
        else:
            self.status_label.setText(f"Dataset: {count} selected image(s)")
        self._gallery.set_paths(list(imported.source_paths))
        self._advisor_panel.set_images(
            list(imported.source_paths), self.trigger_edit.text().strip()
        )
        self._advisor_panel.set_exclusion_count(len(self._advisor_exclusions))

    def _on_dataset_path_edited(self) -> None:
        current = self.data_dir_edit.text().strip()
        if current == (self._applied_train_dir or ""):
            return
        if self._training_running() or self._review_running():
            self.data_dir_edit.blockSignals(True)
            self.data_dir_edit.setText(self._applied_train_dir or "")
            self.data_dir_edit.blockSignals(False)
            self.status_label.setText("Cannot change the dataset while training is running.")
            return
        self._dataset_paths = ()
        self._dataset_scope = "folder"
        if not current:
            self._clear_staging()
            self._applied_train_dir = None
            return
        self.apply_imported_paths((current,))

    def _on_review_saved(self, _written: int) -> None:
        # Captions are written next to the files in data_dir_edit (the train
        # dir). Restaging here would rmtree a directory a live job may own.
        return

    def _update_advisor_hydra_availability(self, *_args) -> None:
        if not hasattr(self, "_advisor_panel"):
            return
        engine = self.engine_combo.currentData() if hasattr(self, "engine_combo") else "standard"
        available = engine != "standard" and not getattr(sys, "frozen", False)
        self._advisor_panel.set_hydra_available(available)

    def _on_trigger_for_advisor(self, *_args) -> None:
        if hasattr(self, "_advisor_panel"):
            self._advisor_panel.refresh_trigger(self.trigger_edit.text().strip())

    def _on_advisor_selection(self, paths: list) -> None:
        self._gallery.clear_selection()
        present = [p for p in paths if p in set(self._dataset_paths)]
        if present:
            self._gallery.set_selected(present)
            self._gallery.jump_to_path(present[0])

    def _on_advisor_review_tags(self) -> None:
        self._right_tabs.setCurrentWidget(self._review_panel)
        self._review_tags()

    def _on_advisor_exclude(self, paths: list) -> None:
        if self._training_running() or self._review_running():
            return
        self._advisor_exclusions.update(str(Path(p).resolve()) for p in paths)
        self._restage_for_advisor()

    def _on_advisor_restore(self) -> None:
        if self._training_running() or self._review_running():
            return
        self._advisor_exclusions.clear()
        self._restage_for_advisor()

    def _restage_for_advisor(self) -> None:
        source = self._dataset_source_paths
        if not source:
            return
        if self._training_running() or self._review_running():
            self.status_label.setText(
                "Cannot change the dataset while training or tag review is running."
            )
            return
        self._start_dataset_worker(source, advisor_restage=True)

    def _clear_staging(self) -> None:
        if not self._staging_dir:
            return
        if self._review_running() or (self._staging_dir == self._leased_staging_dir and self._training_running()):
            return
        shutil.rmtree(self._staging_dir, ignore_errors=True)
        self._staging_dir = None
