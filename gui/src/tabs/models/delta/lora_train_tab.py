import contextlib
import shutil
import signal
import subprocess
import threading
from pathlib import Path

from middleware.src.comfy_matrix import gpu_lease, try_admit
from middleware.src.constants import LOCAL_SOURCE_PATH
from middleware.src.core.gpu_vram_estimate import estimate_job_gb
from middleware.src.core.training_runs import (
    STATUS_CANCEL,
    STATUS_ERROR,
    STATUS_SUCCESS,
)
from middleware.src.models.hooks import DiagnosticsLogger
from middleware.src.models.tuning.lo_ra_tuner import LoRATuner
from middleware.src.models.wrappers.gan_wrapper import GanWrapper
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from gui.src.components.prompt_vocabulary import model_prefix_for
from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import retain_until_stopped

from ....classes.base.base_generative_tab import (
    BaseGenerativeTab,
)
from ._lora_train_config import LoRATrainConfigMixin
from ._lora_train_dataset import LoRATrainDatasetMixin
from ._lora_train_runs import (  # noqa: F401  re-exported for callers and tests
    AdapterRankWorker,
    LoRATrainRunsMixin,
    TrainingReportWorker,
    _rank_utilization_for_run,
)
from ._lora_train_ui import LoRATrainUiMixin
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


class DatasetPrepareWorker(BaseQThreadWorker):
    """Scan and stage a Library/Browse handoff off the GUI thread."""

    def __init__(
        self,
        paths: tuple[str, ...],
        staging_root: Path | None,
        exclusions: frozenset[str] | None = None,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._staging_root = staging_root
        self._exclusions = exclusions
        self.result: ImportedDataset | None = None
        self.discarded = False
        self.review_only = False
        self.trigger: str | None = None

    def _execute(self) -> object:
        self.result = resolve_imported_dataset(
            self._paths, staging_root=self._staging_root, exclusions=self._exclusions
        )
        return self.result

    def cleanup_unclaimed(self) -> None:
        result = self.result
        if self.discarded and result is not None and result.staged and result.train_dir:
            threading.Thread(
                target=shutil.rmtree, args=(result.train_dir,), kwargs={"ignore_errors": True},
                daemon=True, name="itk-unused-dataset-cleanup",
            ).start()


class LoRATrainTab(LoRATrainConfigMixin, LoRATrainUiMixin, LoRATrainRunsMixin, LoRATrainDatasetMixin, BaseGenerativeTab):
    # --- Define Signals for Thread-Safe Communication ---
    update_status_signal = Signal(str)
    # run_dir (#741) is the third payload: the report card (#746) reads
    # the run's events.jsonl when a success carries one ("" otherwise).
    training_finished_signal = Signal(str, str, str)
    run_directory_ready = Signal(str)


    def __init__(self):
        super().__init__()
        self.last_browsed_scan_dir = LOCAL_SOURCE_PATH
        self._lycoris_process: subprocess.Popen | None = None
        self._disposing = False
        self._training_thread: threading.Thread | None = None
        self._dataset_paths: tuple[str, ...] = ()
        self._dataset_scope = "folder"
        self._staging_dir: str | None = None
        self._staging_root: Path | None = None
        self._leased_staging_dir: str | None = None
        self._applied_train_dir: str | None = None
        self._dataset_worker: DatasetPrepareWorker | None = None
        self._advisor_exclusions: set[str] = set()
        self._dataset_source_folder: str | None = None
        self._dataset_source_paths: tuple[str, ...] = ()
        self._group_kill_timer: QTimer | None = None
        self.init_ui()
        self.update_status_signal.connect(self.handle_status_update)
        self.training_finished_signal.connect(self.handle_training_finished)
        self.run_directory_ready.connect(self._live_panel.follow)


    def browse_dataset(self):
        if self._training_running() or self._review_running():
            self.status_label.setText("Cannot replace the dataset while training or tag review is running.")
            return
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Dataset Folder",
            self.last_browsed_scan_dir,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if directory:
            self.last_browsed_scan_dir = directory
            self.apply_imported_paths((directory,))

    def update_ui_visibility(self):
        model_id = self.model_selector.currentData()
        is_gan = model_id == "animegan_v2"
        self.lora_group.setProperty("disclosure_applicable", not is_gan)
        self.apply_disclosure_tier(self._active_disclosure_tier)
        self.cancel_btn.setEnabled(False)

        # PromptEdit chips (#733): base-model quality prefix + trigger tokens
        # mined from past run records (empty until Gate D writes records).
        prefix = None if is_gan else model_prefix_for(model_id)
        trigger_tokens = [] if is_gan else self.prompt_edit.trigger_tokens()
        self.prompt_edit.set_chips([c for c in ([prefix] if prefix else []) + trigger_tokens if c])
        self.prompt_edit.set_meter_model_id("" if is_gan else model_id)

    def cancel_training(self):
        proc = self._lycoris_process
        if proc is not None:
            # The child is its own session, so this does not signal the GUI.
            if not _signal_process_group(proc, signal.SIGTERM):
                proc.terminate()
            self._arm_group_kill(proc)
        else:
            model_id = self.model_selector.currentData()
            if model_id == "animegan_v2":
                GanWrapper.cancel_process()
            else:
                LoRATuner.cancel_process()
        self.cancel_btn.setEnabled(False)
        self.handle_status_update("Cancellation requested...")

    def _arm_group_kill(self, proc) -> None:
        """SIGKILL only if SIGTERM has not exited the session. Tests stop this timer."""
        pid = getattr(proc, "pid", None)
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return
        if self._group_kill_timer is not None:
            self._group_kill_timer.stop()
        timer = QTimer(self)
        timer.setSingleShot(True)

        def _escalate() -> None:
            if proc.poll() is not None:
                return
            if not _signal_process_group(proc, signal.SIGKILL):
                with contextlib.suppress(OSError):
                    proc.kill()

        timer.timeout.connect(_escalate)
        self._group_kill_timer = timer
        timer.start(2000)

    # --- Config Methods ---


    # --- Slots (Main Thread) ---
    @Slot(str)
    def handle_status_update(self, text):
        self.status_label.setText(text)

    @Slot(str, str, str)
    def handle_training_finished(self, status_type, message, run_dir: str = ""):
        if self._disposing:
            return
        self._restore_start_after_training()
        self.cancel_btn.setEnabled(False)
        LoRATuner.is_cancelled = False
        GanWrapper.is_cancelled = False
        if status_type == "success":
            self.status_label.setText(message)
            # #746: the report card replaces the plain success box when the
            # run recorded events; failures degrade back to the old box.
            if not (run_dir and self._show_report_card(run_dir)):
                QMessageBox.information(self, "Success", message)
        elif status_type == "cancel":
            self.status_label.setText("Stopped.")
            QMessageBox.warning(self, "Result", message)
        else:
            self.status_label.setText("Error occurred.")
            QMessageBox.critical(self, "Error", message)


    @Slot(object)
    def _on_report_ready(self, card) -> None:
        worker = self.sender()
        if worker is not getattr(self, "_report_worker", None):
            return
        self._report_worker = None
        if self._disposing:
            return
        if card is None or card.step_count == 0:
            QMessageBox.information(self, "Success", "Training finished and weights saved.")
            return
        from gui.src.components.dialogs.training_report_card_dialog import TrainingReportCardDialog

        dialog = TrainingReportCardDialog(
            card, run_dir=worker.run_dir, parent=self,
            rank_chart_available=worker.rank_available,
        )
        dialog.rank_chart_requested.connect(lambda: self._open_rank_chart(worker.run_dir))
        dialog.start_tournament_requested.connect(self._open_checkpoint_tournament)
        dialog.experiment_requested.connect(self._open_experiment)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()
        self._report_card_dialog = dialog


    @Slot(object)
    def _on_rank_history_ready(self, report: object) -> None:
        worker = self.sender()
        if worker is not getattr(self, "_rank_worker", None):
            return
        self._rank_worker = None
        if self._disposing:
            return
        from middleware.src.core.adapter_reports import RankHistoryReport

        from gui.src.components.dialogs.adapter_rank_chart_dialog import AdapterRankChartDialog

        if not isinstance(report, RankHistoryReport):
            QMessageBox.information(self, "Adapter Geometry", "No adapter checkpoints found for this run.")
            return
        dialog = AdapterRankChartDialog(
            report, run_dir=worker.run_dir, record=worker.record, parent=self
        )
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()
        self._rank_chart_dialog = dialog


    def _restore_start_after_training(self) -> None:
        if self._disposing:
            return
        if self._training_running():
            QTimer.singleShot(25, self, self._restore_start_after_training)
            return
        self._training_thread = None
        self._leased_staging_dir = None
        self.train_btn.setEnabled(True)

    def _review_running(self) -> bool:
        panel = self._review_panel
        workers = [panel._worker, *panel._retained_workers]
        return any(worker is not None and worker.isRunning() for worker in workers)

    def _training_running(self) -> bool:
        thread = self._training_thread
        if thread is not None and thread.is_alive():
            return True
        process = self._lycoris_process
        return process is not None and process.poll() is None

    def start_training_thread(self):
        if self._disposing or self._dataset_worker is not None or self._training_running() or self._review_running():
            return
        self.train_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.status_label.setText("Initializing Training...")
        self._live_panel.begin(int(self.widgets["epochs"].value()))
        params = self.collect()  # Use collect instead of get_params for consistency

        config = {
            "params": params,
            "data_dir": self.data_dir_edit.text(),
            "model_id": self.model_selector.currentData(),
            "rank": self.rank_box.value(),
            "prompt": self.prompt_edit.text(),
            "trigger": self.trigger_edit.text().strip(),
            "output_name": params.get("output_name", "output_lora"),
            "engine": self.engine_combo.currentData(),
        }
        self._leased_staging_dir = self._staging_dir
        thread = threading.Thread(target=self.run_training, kwargs=config, daemon=True)
        self._training_thread = thread
        thread.start()

    def run_training(
        self,
        params,
        data_dir,
        model_id,
        rank,
        prompt,
        output_name,
        engine="standard",
        trigger="",
    ):
        refusal = try_admit(
            "lora-train",
            estimated_gb=estimate_job_gb(
                "lora-train",
                model_id=model_id,
                rank=rank,
                batch_size=(params or {}).get("batch_size", 1),
            ),
        )
        if refusal:
            self.training_finished_signal.emit("error", refusal, "")
            return
        run_dir = None
        try:
            run_dir = self._create_run_record(
                params, data_dir, model_id, rank, prompt, output_name, engine, trigger,
            )
            if run_dir is not None:
                self.run_directory_ready.emit(str(run_dir))
            self._run_training_admitted(
                params, data_dir, model_id, rank, prompt, output_name, engine, trigger,
                run_dir=run_dir,
            )
        finally:
            gpu_lease.release("lora-train")


    def _run_training_admitted(
        self,
        params,
        data_dir,
        model_id,
        rank,
        prompt,
        output_name,
        engine="standard",
        trigger="",
        run_dir: Path | None = None,
    ):
        trigger_word = (trigger or "").strip()
        instance_prompt = combine_trigger_and_prompt(trigger_word, prompt)
        if engine != "standard" and model_id != "animegan_v2":
            self._run_lycoris_training(
                data_dir,
                model_id,
                trigger_word or prompt,
                output_name,
                engine,
                epochs=int(params.get("epochs", 5)),
                batch_size=int(params.get("batch_size", 1)),
                learning_rate=float(params.get("learning_rate", 1e-4)),
                rank=rank,
                run_dir=run_dir,
            )
            return

        gan = None
        diagnostics = None
        try:
            if model_id == "animegan_v2":
                self.update_status_signal.emit("Starting GAN Fine-tuning...")
                gan = GanWrapper()
                gan.train(
                    style_data_dir=data_dir,
                    epochs=params.get("epochs", 5),
                    lr=params.get("learning_rate", 1e-4),
                    batch_size=params.get("batch_size", 1),
                )
                is_cancelled = GanWrapper.is_cancelled
            else:
                self.update_status_signal.emit(
                    f"Loading Diffusion Model: {model_id}..."
                )
                if run_dir is not None:
                    # #741: in-process JSONL event sink; TB/W&B stay off on
                    # the GUI path (events.jsonl is the analysis contract).
                    diagnostics = DiagnosticsLogger(
                        run_name=Path(run_dir).name,
                        use_tensorboard=False,
                        use_wandb=False,
                        jsonl_path=str(Path(run_dir) / "events.jsonl"),
                    )
                tuner = LoRATuner(model_id=model_id, output_dir=output_name)
                tuner.configure_lora(rank=rank)
                self.update_status_signal.emit("Training started...")
                tuner.train(
                    data_dir=data_dir,
                    instance_prompt=instance_prompt,
                    epochs=params.get("epochs", 5),
                    learning_rate=params.get("learning_rate", 1e-4),
                    batch_size=params.get("batch_size", 1),
                    diagnostics=diagnostics,
                )
                is_cancelled = LoRATuner.is_cancelled

            if is_cancelled:
                self._finish_run_record(run_dir, STATUS_CANCEL, output_name, engine)
                self.training_finished_signal.emit(
                    "cancel", "Training process was stopped by the user.", str(run_dir or "")
                )
            else:
                self._finish_run_record(run_dir, STATUS_SUCCESS, output_name, engine)
                self.training_finished_signal.emit(
                    "success", "Training finished and weights saved.", str(run_dir or "")
                )
        except Exception as e:
            self.update_status_signal.emit(f"Error: {str(e)}")
            self._finish_run_record(run_dir, STATUS_ERROR, output_name, engine, error=str(e))
            self.training_finished_signal.emit("error", str(e), str(run_dir or ""))
        finally:
            if diagnostics is not None:
                diagnostics.close()
            if gan is not None:
                gan.unload()


    def _inspect_safetensors(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select .safetensors File",
            self.last_browsed_scan_dir,
            "Safetensors models (*.safetensors)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not path:
            return
        from gui.src.components.dialogs.safetensors_inspector_dialog import SafetensorsInspectorDialog
        SafetensorsInspectorDialog(path=path, parent=self).exec()

    def apply_imported_paths(self, paths: tuple[str, ...]) -> None:
        if self._disposing:
            return
        if self._training_running() or self._review_running():
            self.status_label.setText("Cannot replace the dataset while training or tag review is running.")
            return
        self._start_dataset_worker(paths)

    def _start_dataset_worker(self, paths: tuple[str, ...], *, review_only: bool = False, advisor_restage: bool = False) -> None:
        from gui.src.helpers.worker_teardown import stop_worker

        if not review_only and not advisor_restage:
            self._dataset_source_paths = paths
            self._advisor_exclusions.clear()
            self._dataset_source_folder = None
        previous = self._dataset_worker
        if previous is not None:
            previous.discarded = True
            stop_worker(previous, join=False)
        self.status_label.setText("Preparing dataset…")
        worker = DatasetPrepareWorker(
            paths,
            self._staging_root,
            exclusions=frozenset(self._advisor_exclusions) if self._advisor_exclusions else None,
        )
        worker.review_only = review_only
        worker.trigger = self.trigger_edit.text().strip() or None
        worker.finished.connect(self._on_dataset_prepared)
        self._dataset_worker = worker
        worker.start()
        retain_until_stopped(worker, worker.cleanup_unclaimed)


    # --- Dataset advisor (#744) ---


    def disposal_ready(self) -> bool:
        return not self._training_running()


    def closeEvent(self, event) -> None:
        self.prepare_dispose()
        super().closeEvent(event)

    def _review_tags(self) -> None:
        if self._disposing or self._dataset_worker is not None or self._training_running() or self._review_running():
            return
        data_dir = self.data_dir_edit.text().strip()
        if not data_dir:
            QMessageBox.warning(self, "Review Tags", "Select a valid dataset first.")
            return
        self._start_dataset_worker((data_dir,), review_only=True)


    @Slot(object)
    def _on_dataset_prepared(self, imported) -> None:
        sender = self.sender()
        if self._disposing or (sender is not None and sender is not self._dataset_worker):
            return
        self._dataset_worker = None
        if not isinstance(imported, ImportedDataset):
            self.status_label.setText("Dataset preparation failed.")
            return
        if imported.train_dir is None:
            if sender is not None and not sender.review_only:
                self._apply_resolved(imported)
            self.status_label.setText("No usable images in that selection.")
            return
        if sender is not None and sender.review_only:
            if not imported.source_paths:
                self.status_label.setText("No usable images in that selection.")
                return
            self._right_tabs.setCurrentWidget(self._review_panel)
            self._review_panel.start_review(
                [Path(p) for p in imported.source_paths], trigger=sender.trigger,
            )
            return
        self._apply_resolved(imported)

    @Slot(str)
    def _open_experiment(self, run_dir: str) -> None:
        from gui.src.components.dialogs.training_experiment_dialog import TrainingExperimentDialog
        dialog = TrainingExperimentDialog(run_dir, parent=self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    @Slot(str)
    def _open_checkpoint_tournament(self, run_dir: str) -> None:
        """#747: blind ELO over the run's checkpoint sample grids."""
        from gui.src.components.dialogs.checkpoint_tournament_dialog import (
            CheckpointTournamentDialog,
        )

        dialog = CheckpointTournamentDialog(run_dir, parent=self)
        dialog.promote_requested.connect(self._forward_promoted_pin)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()
        self._tournament_dialog = dialog

    @Slot(object)
    def _forward_promoted_pin(self, pin) -> None:
        """Hand the tournament winner to the workspace spine so Generate's
        adapter can be set from the pin (duck-typed: whoever hosts a
        ComparisonSpine gets it)."""
        host = self.parent()
        while host is not None:
            note = getattr(host, "note_run", None)
            if callable(note):
                note(pin)
                return
            host = host.parent()
        window = self.window()
        if window is None:
            return
        from gui.src.tabs.models.dl_comparison_spine import ComparisonSpine

        spine = window.findChild(ComparisonSpine)
        if spine is not None:
            spine.note_run(pin)


