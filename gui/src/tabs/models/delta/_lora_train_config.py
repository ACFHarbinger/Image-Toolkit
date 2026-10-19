"""Config collection/restore, summaries and disposal for LoRATrainTab."""
import shutil
import threading

from middleware.src.constants import LOCAL_SOURCE_PATH

from ._lora_train_runs import (  # noqa: F401  re-exported for callers and tests
    AdapterRankWorker,
    LoRATrainRunsMixin,
    TrainingReportWorker,
    _rank_utilization_for_run,
)
from .lora_dataset_staging import (  # noqa: F401  re-exported for callers and tests
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


class LoRATrainConfigMixin:
    """Config collection/restore, summaries and disposal for LoRATrainTab."""

    def collect(self) -> dict:
        data = super().collect()
        data["dataset_folder"] = self.data_dir_edit.text()
        data["dataset_paths"] = list(self._dataset_paths)
        data["dataset_scope"] = self._dataset_scope
        data["trigger_prompt"] = self.prompt_edit.text()
        data["trigger_token"] = self.trigger_edit.text()
        data["lora_rank"] = self.rank_box.value()
        return data

    def set_config(self, config: dict):
        if self._disposing or self._training_running() or self._review_running():
            return
        super().set_config(config)
        if "trigger_prompt" in config:
            self.prompt_edit.setText(config["trigger_prompt"])
        if "trigger_token" in config:
            self.trigger_edit.setText(config["trigger_token"])
        if "lora_rank" in config:
            self.rank_box.setValue(config["lora_rank"])
        saved_paths = tuple(config.get("dataset_paths") or ())
        if saved_paths and config.get("dataset_scope") == "selection":
            self.apply_imported_paths(saved_paths)
        elif "dataset_folder" in config:
            folder = config["dataset_folder"]
            self.data_dir_edit.setText(folder)
            self._dataset_scope = "folder"
            self._dataset_paths = ()
            self.apply_imported_paths((folder,) if folder else ())

    def get_default_config(self) -> dict:
        defaults = super().get_default_config()
        defaults.update(
            {
                "dataset_folder": LOCAL_SOURCE_PATH,
                "dataset_paths": [],
                "dataset_scope": "folder",
                "trigger_prompt": "1girl, style of my_char",
                "trigger_token": "",
                "lora_rank": 4,
            }
        )
        return defaults

    def prepare_dispose(self) -> None:
        """Nonblocking cancel used by workspace disposal (no closeEvent)."""
        from gui.src.helpers.worker_teardown import stop_worker

        if self._disposing:
            return
        self._disposing = True
        self._review_panel.stop_review(join=False)
        self._advisor_panel.stop()
        if self._dataset_worker is not None:
            self._dataset_worker.discarded = True
            stop_worker(self._dataset_worker, join=False)
        self.cancel_training()
        thread = self._training_thread
        leased = self._leased_staging_dir
        staging = self._staging_dir
        review_workers = tuple(self._review_panel._retained_workers)
        if (thread is not None and thread.is_alive()) or any(w.isRunning() for w in review_workers):
            def _cleanup_after_job() -> None:
                if thread is not None:
                    thread.join()
                for worker in review_workers:
                    worker.wait()
                for directory in {leased, staging}:
                    if directory:
                        shutil.rmtree(directory, ignore_errors=True)

            threading.Thread(
                target=_cleanup_after_job,
                daemon=True,
                name="itk-train-dataset-cleanup",
            ).start()
            self._leased_staging_dir = None
            self._staging_dir = None
        else:
            self._clear_staging()

    def get_effective_config_summary(self) -> str:
        """Return resolved one-line config to run (#731)."""
        model_id = self.model_selector.currentData() or self.model_selector.currentText()
        engine = self.engine_combo.currentText() if hasattr(self, "engine_combo") else "Standard"
        engine_id = self.engine_combo.currentData() if hasattr(self, "engine_combo") else "standard"
        epochs = self.widgets["epochs"].value() if "epochs" in self.widgets else 5
        batch = self.widgets["batch_size"].value() if "batch_size" in self.widgets else 1
        lr = self.widgets["learning_rate"].value() if "learning_rate" in self.widgets else 1e-4
        rank = self.rank_box.value() if hasattr(self, "rank_box") else 4
        trigger = self.trigger_edit.text().strip() if hasattr(self, "trigger_edit") else ""
        trigger_str = f"'{trigger}'" if trigger else "(none)"
        prompt = self.prompt_edit.text().strip() if hasattr(self, "prompt_edit") else ""
        folder = self.data_dir_edit.text().strip() if hasattr(self, "data_dir_edit") else ""
        folder_str = f" · Dataset: '{folder}'" if folder else ""
        if engine_id == "standard":
            inst_prompt = combine_trigger_and_prompt(trigger, prompt)
            prompt_str = f" · Instance Prompt: '{inst_prompt}'" if inst_prompt else ""
        else:
            effective_trigger = trigger or prompt
            trigger_str = repr(effective_trigger) if effective_trigger else "(none)"
            prompt_str = ""
        overrides = ""
        if hasattr(self, "_advisor_panel"):
            pending = self._advisor_panel.hydra_overrides()
            if pending:
                overrides = f" · Advisor overrides: {' '.join(pending)}"
        return f"Model: {model_id} · Engine: {engine} · Epochs: {epochs} · Batch: {batch} · LR: {lr:g} · Rank: {rank} · Trigger: {trigger_str}{prompt_str}{folder_str}{overrides}"
