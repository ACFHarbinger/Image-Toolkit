"""Run records, report/rank/tournament dialogs and the LyCORIS runner for LoRATrainTab."""
import subprocess
import sys
from pathlib import Path

from middleware.src.constants import ROOT_DIR
from middleware.src.core.training_runs import (
    STATUS_CANCEL,
    STATUS_ERROR,
    STATUS_SUCCESS,
    default_runs_root,
    finish_run,
    new_run_id,
    start_run,
)

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import retain_until_stopped

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


def _rank_utilization_for_run(run_dir: str):
    """#743: RankUtilization for the #746 card, from the run's checkpoints.

    Pure-type validation guards against the GUI test mock tree — a fake
    rank_history result degrades to (None, availability) instead of
    poisoning the card.
    """
    from middleware.src.core.adapter_reports import RankHistoryReport
    from middleware.src.core.training_report import RankUtilization
    from middleware.src.core.training_runs import read_run_record

    record = read_run_record(run_dir)
    if record is None:
        return None, False
    lora_path = str(record.get("lora_path") or "")
    if not lora_path:
        return None, False
    output = Path(lora_path)
    if output.is_file():
        output = output.parent
    try:
        from middleware.src.models.hooks.adapter_geometry import rank_history

        report = rank_history(output)
    except Exception:
        # Artifacts may still chart fine; the chart worker re-tries.
        return None, True
    if not isinstance(report, RankHistoryReport):
        return None, True
    available = bool(report.snapshots)
    latest = report.latest()
    utilization = latest.utilization() if latest is not None else None
    return (utilization if isinstance(utilization, RankUtilization) else None), available


class TrainingReportWorker(BaseQThreadWorker):
    def __init__(self, run_dir: str, findings) -> None:
        super().__init__()
        self.run_dir = run_dir
        self.findings = findings
        self.rank = None
        self.rank_available = False

    def _execute(self):
        from middleware.src.core.training_report import generate_training_report
        from middleware.src.core.training_runs import iter_events

        self.rank, self.rank_available = _rank_utilization_for_run(self.run_dir)
        return generate_training_report(
            iter_events(self.run_dir),
            rank_utilization=self.rank,
            dataset_findings=self.findings,
        )


class AdapterRankWorker(BaseQThreadWorker):
    """#743: rank history for the chart dialog, off the GUI thread."""

    def __init__(self, run_dir: str) -> None:
        super().__init__()
        self.run_dir = run_dir
        self.record = None

    def _execute(self) -> object:
        from middleware.src.core.adapter_reports import RankHistoryReport
        from middleware.src.core.training_runs import read_run_record

        self.record = read_run_record(self.run_dir) or {}
        lora_path = str((self.record or {}).get("lora_path") or "")
        if not lora_path:
            return RankHistoryReport(output_dir="", note="run has no adapter artifact")
        output = Path(lora_path)
        if output.is_file():
            output = output.parent
        try:
            from middleware.src.models.hooks.adapter_geometry import rank_history

            report = rank_history(output)
        except Exception as exc:
            report = RankHistoryReport(output_dir=str(output), note=f"rank analysis failed: {exc}")
        return report if isinstance(report, RankHistoryReport) else None


class LoRATrainRunsMixin:
    """LoRATrainTab methods for run bookkeeping and post-run review."""

    def _show_report_card(self, run_dir: str) -> bool:
        """Generate the #746 card from the run's events and show it."""
        panel = getattr(self, "_advisor_panel", None)
        findings = panel.findings() if panel is not None and hasattr(panel, "findings") else []
        worker = TrainingReportWorker(run_dir, findings)
        worker.finished.connect(self._on_report_ready)
        self._report_worker = worker
        retain_until_stopped(worker)
        worker.start()
        return True


    def _open_rank_chart(self, run_dir: str) -> None:
        """#743: compute rank history off-thread, then open the chart."""
        if self._disposing or getattr(self, "_rank_worker", None) is not None:
            return
        worker = AdapterRankWorker(run_dir)
        worker.finished.connect(self._on_rank_history_ready)
        self._rank_worker = worker
        retain_until_stopped(worker)
        worker.start()


    def _create_run_record(
        self, params, data_dir, model_id, rank, prompt, output_name, engine, trigger,
    ) -> Path | None:
        """Run record + events dir for this training launch (#741).

        Worker-thread context (file I/O off the GUI thread). A failure to
        record must never block training itself, so it degrades to None and
        the run proceeds unrecorded with a status note.
        """
        trigger_word = (trigger or "").strip()
        try:
            return start_run(
                runs_root=default_runs_root(),
                run_id=new_run_id(output_name),
                output_name=output_name,
                engine=engine or "standard",
                model_id=model_id or "",
                trigger_word=trigger_word,
                instance_prompt=combine_trigger_and_prompt(trigger_word, prompt),
                config={
                    "rank": rank,
                    "epochs": int(params.get("epochs", 5)),
                    "batch_size": int(params.get("batch_size", 1)),
                    "learning_rate": float(params.get("learning_rate", 1e-4)),
                    "data_dir": data_dir,
                    "output_name": output_name,
                },
            )
        except OSError as exc:
            self.update_status_signal.emit(f"Run recording unavailable: {exc}")
            return None

    def _finish_run_record(
        self, run_dir: Path | None, status: str, output_name: str, engine: str, error: str | None = None,
    ) -> None:
        if run_dir is None:
            return
        try:
            finish_run(
                run_dir, status,
                lora_path=self._resolve_lora_path(output_name, engine), error=error,
            )
        except OSError as exc:
            self.update_status_signal.emit(f"Could not finalize run record: {exc}")

    @staticmethod
    def _resolve_lora_path(output_name: str, engine: str) -> str:
        out = Path(output_name or "output_lora")
        if engine != "standard" and not out.is_absolute():
            out = ROOT_DIR / out
        out = out.resolve()
        if engine != "standard":
            weights = out / "lora_weights.safetensors"
            return str(weights if weights.is_file() else out)
        return str(out)

    def _run_lycoris_training(
        self,
        data_dir: str,
        model_id: str,
        prompt: str,
        output_name: str,
        engine: str,
        *,
        epochs: int = 5,
        batch_size: int = 1,
        learning_rate: float = 1e-4,
        rank: int = 4,
        run_dir: Path | None = None,
    ) -> None:
        """Content Gen §1.3: LyCORIS (LoCon/LoHa/LoKr) training.

        Routes through the already-built LoRATunerV2 pipeline
        (middleware/src/pipeline/anime_training_pipeline.py) via this
        project's own Hydra CLI dispatcher, rather than re-implementing
        dataset/tuner construction here — that pipeline already handles
        aspect-ratio bucketing, caption building, and LyCORIS dispatch
        (LoRATunerV2 already supports 'locon'/'loha'/'lokr'/'dylora' via
        `cfg.method == "lycoris"`; only GUI exposure was missing).

        The four visible training controls are forwarded as Hydra overrides
        (#726). The third positional (``prompt``) is Hydra
        ``data.trigger_word`` — the activation token, not the instance
        prompt. The lycoris_* presets leave max_train_steps null, so
        max_train_epochs is authoritative in LoRATunerV2's step math.
        """
        self.update_status_signal.emit(
            f"Launching LyCORIS ({engine}) training via anime_training_pipeline..."
        )
        if getattr(sys, "frozen", False):
            self.update_status_signal.emit(
                "Error: LyCORIS training spawns the source checkout's Hydra "
                "dispatcher and is not available in the packaged build."
            )
            self._finish_run_record(run_dir, STATUS_ERROR, output_name, engine,
                                    error="LyCORIS training requires a source checkout.")
            self.training_finished_signal.emit(
                "error", "LyCORIS training requires a source checkout.", str(run_dir or "")
            )
            return
        cmd = [
            sys.executable,
            "-m",
            "middleware.controllers.hydra_dispatch",
            "command=train",
            f"training=lycoris_{engine}",
            f"model.model_id={model_id}",
            f"data.images_dir={data_dir}",
            f"data.trigger_word={prompt}",
            f"output_dir={output_name}",
            f"training.rank={rank}",
            f"training.train_batch_size={batch_size}",
            f"training.max_train_epochs={epochs}",
            f"optimizer.unet_lr={learning_rate}",
        ]
        if run_dir is not None:
            # #741: the subprocess writes its own events.jsonl into the run
            # dir (same contract as the in-process path) — no stdout parsing.
            cmd.append(f"logging.run_dir={run_dir}")
        # #744: advisor-queued Hydra overrides (e.g. pipeline.run_captioning=true).
        for fragment in self._advisor_panel.hydra_overrides():
            if fragment not in cmd:
                cmd.append(fragment)
        try:
            self._lycoris_process = subprocess.Popen(
                cmd,
                cwd=str(ROOT_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            assert self._lycoris_process.stdout is not None
            for line in self._lycoris_process.stdout:
                line = line.rstrip()
                if line:
                    self.update_status_signal.emit(line[-200:])
            returncode = self._lycoris_process.wait()

            if returncode == 0:
                self._finish_run_record(run_dir, STATUS_SUCCESS, output_name, engine)
                self.training_finished_signal.emit(
                    "success", "LyCORIS training finished and weights saved.", str(run_dir or "")
                )
            elif returncode < 0:
                # Negative = killed by signal (terminate()/Cancel button).
                self._finish_run_record(run_dir, STATUS_CANCEL, output_name, engine)
                self.training_finished_signal.emit(
                    "cancel", "Training process was stopped by the user.", str(run_dir or "")
                )
            else:
                self._finish_run_record(
                    run_dir, STATUS_ERROR, output_name, engine,
                    error=f"Training process exited with code {returncode}.",
                )
                self.training_finished_signal.emit(
                    "error", f"Training process exited with code {returncode}.",
                    str(run_dir or ""),
                )
        except Exception as e:
            self.update_status_signal.emit(f"Error: {str(e)}")
            self._finish_run_record(run_dir, STATUS_ERROR, output_name, engine, error=str(e))
            self.training_finished_signal.emit("error", str(e), str(run_dir or ""))
        finally:
            self._lycoris_process = None
