import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import NamedTuple

from backend.src.comfy_matrix import gpu_lease, try_admit
from backend.src.constants import LOCAL_SOURCE_PATH, ROOT_DIR
from backend.src.core.training_runs import (
    STATUS_CANCEL,
    STATUS_ERROR,
    STATUS_SUCCESS,
    default_runs_root,
    finish_run,
    new_run_id,
    start_run,
)
from backend.src.models.hooks import DiagnosticsLogger
from backend.src.models.tuning.lo_ra_tuner import LoRATuner
from backend.src.models.wrappers.gan_wrapper import GanWrapper
from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.prompt_edit import PromptEdit
from gui.src.components.prompt_vocabulary import default_vocabulary, model_prefix_for
from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import retain_until_stopped

from ....classes.base.base_generative_tab import (
    TIER_ADVANCED,
    TIER_SIMPLE,
    TIER_STANDARD,
    BaseGenerativeTab,
    model_choice_label,
)

# Content Gen §1.3: LyCORIS variants (LoCon/LoHa/LoKr), each a Hydra config
# preset under backend/config/training/. "standard" keeps the existing
# LoRATuner (legacy) path byte-for-byte unchanged; the three LyCORIS
# entries route through the already-built LoRATunerV2 pipeline
# (backend/src/pipeline/anime_training_pipeline.py) via the project's own
# Hydra CLI dispatcher, rather than re-implementing dataset/tuner
# construction inline here.
_TRAINING_ENGINES = [
    ("Standard (LoRA)", "standard"),
    ("LyCORIS: LoCon (style-bound characters)", "locon"),
    ("LyCORIS: LoHa (small datasets)", "loha"),
    ("LyCORIS: LoKr (tiny datasets / storage-constrained)", "lokr"),
]


_DATASET_IMAGE_EXTS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".bmp"})


class ImportedDataset(NamedTuple):
    train_dir: str | None
    source_paths: tuple[str, ...]
    scope: str
    staged: bool


def combine_trigger_and_prompt(trigger: str, prompt: str) -> str:
    """Prepend the activation token to the instance prompt when missing."""
    trigger = trigger.strip()
    prompt = prompt.strip()
    if not trigger:
        return prompt
    tokens = [part.strip() for part in prompt.split(",") if part.strip()]
    if trigger in tokens:
        return prompt
    return f"{trigger}, {prompt}" if prompt else trigger


def _image_paths_under(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(
            child
            for child in path.iterdir()
            if child.is_file() and child.suffix.lower() in _DATASET_IMAGE_EXTS
        )
    if path.is_file() and path.suffix.lower() in _DATASET_IMAGE_EXTS:
        return [path]
    return []


def _existing_images(paths: list[Path]) -> list[Path]:
    images: list[Path] = []
    for path in paths:
        if path.is_dir():
            images.extend(_image_paths_under(path))
        elif path.is_file() and path.suffix.lower() in _DATASET_IMAGE_EXTS:
            images.append(path)
    unique: list[Path] = []
    seen: set[Path] = set()
    for image in images:
        key = image.resolve()
        if key in seen:
            continue
        seen.add(key)
        unique.append(image)
    return unique


def _exclusive_parent(unique: list[Path]) -> Path | None:
    parents = {image.resolve().parent for image in unique}
    if len(parents) != 1:
        return None
    parent = next(iter(parents))
    siblings = {child.resolve() for child in _image_paths_under(parent)}
    if siblings == {image.resolve() for image in unique}:
        return parent
    return None


def _unique_staged_name(src: Path, used_names: set[str], used_stems: set[str]) -> str:
    name = src.name
    if name not in used_names and Path(name).stem not in used_stems:
        return name
    stem, suffix = src.stem, src.suffix
    name = f"{src.parent.name}_{stem}{suffix}"
    extra = 2
    while name in used_names or Path(name).stem in used_stems:
        name = f"{src.parent.name}_{stem}_{extra}{suffix}"
        extra += 1
    return name


def _stage_images(unique: list[Path], staging_root: Path | None) -> Path | None:
    staging_root = staging_root or Path.home() / "Downloads" / "Data" / "Tests"
    staging_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="itk-train-dataset-", dir=str(staging_root)))
    used_names: set[str] = set()
    used_stems: set[str] = set()
    for src in unique:
        if not src.is_file():
            continue
        name = _unique_staged_name(src, used_names, used_stems)
        used_names.add(name)
        used_stems.add(Path(name).stem)
        (staging / name).symlink_to(src.resolve())
        caption = src.with_suffix(".txt")
        if caption.is_file():
            (staging / Path(name).with_suffix(".txt")).symlink_to(caption.resolve())
    has_image = any(
        child.is_file() and child.suffix.lower() in _DATASET_IMAGE_EXTS
        for child in staging.iterdir()
    )
    if not has_image:
        shutil.rmtree(staging, ignore_errors=True)
        return None
    return staging


def resolve_imported_dataset(
    paths: tuple[str, ...],
    *,
    staging_root: Path | None = None,
    exclusions: frozenset[str] | None = None,
) -> ImportedDataset:
    """Map a handoff to the exact files training and Review Tags will see.

    A single directory stays folder-wide (Extractor / Browse) unless
    *exclusions* are set — excluded files must not remain visible to a
    folder-scoped training run, so the kept images fall through to the
    explicit-selection staging path below. Explicit file selections are the
    training set: the parent is reused only when it contains nothing else,
    otherwise the selection is staged so siblings and other directories
    cannot leak in. Missing or non-image paths are dropped before any
    symlink is created.
    """
    if not paths:
        return ImportedDataset(None, (), "selection", False)

    resolved = [Path(item) for item in paths]
    if len(resolved) == 1 and resolved[0].is_dir():
        images = _image_paths_under(resolved[0])
        if not exclusions:
            return ImportedDataset(str(resolved[0]), tuple(str(p) for p in images), "folder", False)
        resolved = [p for p in images if str(p.resolve()) not in exclusions]

    unique = _existing_images(resolved)
    if exclusions:
        unique = [p for p in unique if str(p.resolve()) not in exclusions]
    if not unique:
        return ImportedDataset(None, (), "selection", False)

    parent = _exclusive_parent(unique)
    if parent is not None:
        return ImportedDataset(str(parent), tuple(str(p) for p in unique), "selection", False)

    staging = _stage_images(unique, staging_root)
    if staging is None:
        return ImportedDataset(None, (), "selection", False)
    return ImportedDataset(str(staging), tuple(str(p) for p in unique), "selection", True)


def dataset_folder_from_paths(
    paths: tuple[str, ...],
    *,
    staging_root: Path | None = None,
) -> str | None:
    """Train directory for a handoff. Exact file selections are staged."""
    return resolve_imported_dataset(paths, staging_root=staging_root).train_dir


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


class TrainingReportWorker(BaseQThreadWorker):
    def __init__(self, run_dir: str, findings) -> None:
        super().__init__()
        self.run_dir = run_dir
        self.findings = findings

    def _execute(self):
        from backend.src.core.training_report import generate_training_report
        from backend.src.core.training_runs import iter_events

        return generate_training_report(iter_events(self.run_dir), dataset_findings=self.findings)


class LoRATrainTab(BaseGenerativeTab):
    # --- Define Signals for Thread-Safe Communication ---
    update_status_signal = Signal(str)
    # run_dir (#741) is the third payload: the report card (#746) reads
    # the run's events.jsonl when a success carries one ("" otherwise).
    training_finished_signal = Signal(str, str, str)

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
        self.init_ui()
        self.update_status_signal.connect(self.handle_status_update)
        self.training_finished_signal.connect(self.handle_training_finished)

    def init_ui(self):
        layout = QFormLayout()

        # --- Model Selection ---
        self.model_selector = QComboBox()
        models = [
            (
                "Illustrious XL V2.0 (Base SDXL)",
                "stabilityai/stable-diffusion-xl-base-1.0",
            ),
            (
                "Illustrious Lumina (Base SDXL)",
                "stabilityai/stable-diffusion-xl-base-1.0",
            ),
            ("Anything V3", "ckpt/anything-v3.0"),
            ("Anything V4.5", "ckpt/anything-v4.5"),
            ("Anything V5", "stablediffusionapi/anything-v5"),
            ("Waifu Diffusion v1.4", "hakurei/waifu-diffusion"),
            ("Counterfeit V2.5", "gsdf/Counterfeit-V2.5"),
            ("Animagine XL 3.1", "cagliostrolab/animagine-xl-3.1"),
            ("Animagine XL 4.0", "cagliostrolab/animagine-xl-4.0"),
            ("AnimeGANv2", "animegan_v2"),
        ]
        for name, model_id in models:
            self.model_selector.addItem(model_choice_label(name, model_id), model_id)

        self.add_param_widget(layout, "Base Model:", self.model_selector, "model_id", tier=TIER_SIMPLE)
        self.model_selector.currentIndexChanged.connect(self.update_ui_visibility)

        # Dataset Folder
        folder_container = QWidget()
        self.tag_field(folder_container, tier=TIER_SIMPLE)
        folder_layout = QHBoxLayout(folder_container)
        folder_layout.setContentsMargins(0, 0, 0, 0)

        self.data_dir_edit = QLineEdit(self.last_browsed_scan_dir)
        self.data_dir_edit.editingFinished.connect(self._on_dataset_path_edited)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_dataset)

        folder_layout.addWidget(self.data_dir_edit)
        folder_layout.addWidget(self.browse_btn)
        layout.addRow("Dataset Folder:", folder_container)

        self.add_param_widget(
            layout, "Output Name:", QLineEdit("my_model"), "output_name", tier=TIER_SIMPLE
        )

        # --- Training Engine (Content Gen §1.3: LyCORIS variants) ---
        self.engine_combo = QComboBox()
        for name, engine_id in _TRAINING_ENGINES:
            self.engine_combo.addItem(name, engine_id)
        self.engine_combo.setToolTip(
            "Standard uses this project's original LoRA trainer, unchanged.\n"
            "LyCORIS options route through the LoRATunerV2 pipeline (Hydra\n"
            "presets under backend/config/training/) for LoCon/LoHa/LoKr\n"
            "adaptation instead of plain LoRA — see content_generation.md §1.3."
        )
        self.add_param_widget(layout, "Training Engine:", self.engine_combo, "engine", tier=TIER_ADVANCED)

        # --- Dynamic Configs ---
        self.lora_group = QWidget()
        self.tag_field(self.lora_group, tier=TIER_STANDARD)
        lora_layout = QFormLayout(self.lora_group)
        self.prompt_edit = PromptEdit("1girl, style of my_char")
        self.prompt_edit.set_vocabulary(default_vocabulary())
        self.tag_field(self.prompt_edit, tier=TIER_STANDARD)
        self.trigger_edit = QLineEdit()
        self.trigger_edit.setPlaceholderText("activation token only — not the instance prompt")
        self.tag_field(self.trigger_edit, tier=TIER_STANDARD)
        self.rank_box = QSpinBox()
        self.rank_box.setValue(4)
        self.tag_field(self.rank_box, tier=TIER_ADVANCED)

        lora_layout.addRow("Instance Prompt:", self.prompt_edit)
        lora_layout.addRow("Trigger Token:", self.trigger_edit)
        lora_layout.addRow("LoRA Rank:", self.rank_box)
        layout.addRow(self.lora_group)

        # Common Params
        self.add_param_widget(
            layout, "Epochs:", QSpinBox(minimum=1, value=5, maximum=100), "epochs", tier=TIER_STANDARD
        )
        self.add_param_widget(
            layout,
            "Batch Size:",
            QSpinBox(minimum=1, value=1, maximum=32),
            "batch_size",
            tier=TIER_STANDARD,
        )

        lr_box = QDoubleSpinBox()
        lr_box.setRange(1e-6, 1e-3)
        lr_box.setValue(1e-4)
        lr_box.setDecimals(6)
        self.add_param_widget(layout, "Learning Rate:", lr_box, "learning_rate", tier=TIER_STANDARD)

        # Connect live changes to effective-config notifications
        self.data_dir_edit.textChanged.connect(lambda *_: self.notify_effective_config_changed())
        for field in (self.prompt_edit, self.trigger_edit):
            sig = getattr(field, "promptChanged", None) or getattr(field, "textChanged", None)
            if sig is not None:
                sig.connect(lambda *_: self.notify_effective_config_changed())
        self.rank_box.valueChanged.connect(lambda *_: self.notify_effective_config_changed())
        self.model_selector.currentIndexChanged.connect(lambda *_: self.notify_effective_config_changed())
        self.engine_combo.currentIndexChanged.connect(lambda *_: self.notify_effective_config_changed())

        # --- Action Buttons ---
        button_container = QWidget()
        self.tag_field(button_container, tier=TIER_SIMPLE)
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        self.train_btn = QPushButton("Start Training")
        self.cancel_btn = QPushButton("Cancel")
        self.train_btn.clicked.connect(self.start_training_thread)
        self.cancel_btn.clicked.connect(self.cancel_training)
        button_layout.addWidget(self.train_btn)
        button_layout.addWidget(self.cancel_btn)

        inspect_btn = QPushButton("Inspect .safetensors...")
        inspect_btn.setToolTip("Open a .safetensors file and view its metadata")
        inspect_btn.clicked.connect(self._inspect_safetensors)
        button_layout.addWidget(inspect_btn)

        review_tags_btn = QPushButton("Review Tags...")
        review_tags_btn.setToolTip(
            "Run the WD14 auto-tagger in the dataset panel — does not block this form"
        )
        review_tags_btn.clicked.connect(self._review_tags)
        button_layout.addWidget(review_tags_btn)

        layout.addRow(button_container)
        self.cancel_btn.setEnabled(False)
        self.status_label = QLabel("Ready")
        layout.addRow(self.status_label)


        form_host = QWidget()
        form_host.setLayout(layout)
        from gui.src.components.dialogs.dataset_advisor_panel import AdvisorPanel
        from gui.src.components.dialogs.tag_review_panel import TagReviewPanel
        from gui.src.components.virtual_gallery.widget import VirtualGallery

        # #744: contact sheet under the form on the left; Advisor and Review
        # Tags share the right side as tabs (the panel object is unchanged).
        self._gallery = VirtualGallery()
        gallery_box = QGroupBox("Dataset Contact Sheet")
        gallery_layout = QVBoxLayout(gallery_box)
        gallery_layout.setContentsMargins(4, 4, 4, 4)
        gallery_layout.addWidget(self._gallery)
        left_split = QSplitter(Qt.Orientation.Vertical)
        left_split.addWidget(form_host)
        left_split.addWidget(gallery_box)
        left_split.setStretchFactor(0, 3)
        left_split.setStretchFactor(1, 2)

        self._review_panel = TagReviewPanel(modal_chrome=False)
        self._review_panel.review_saved.connect(self._on_review_saved)

        self._advisor_panel = AdvisorPanel()
        self._advisor_panel.exclude_requested.connect(self._on_advisor_exclude)
        self._advisor_panel.restore_requested.connect(self._on_advisor_restore)
        self._advisor_panel.selection_requested.connect(self._on_advisor_selection)
        self._advisor_panel.review_tags_requested.connect(self._on_advisor_review_tags)
        self._advisor_panel.set_training_guard(self._training_running)
        self._right_tabs = QTabWidget()
        self._right_tabs.addTab(self._advisor_panel, "Advisor")
        self._right_tabs.addTab(self._review_panel, "Review Tags")
        self._update_advisor_hydra_availability()
        self.engine_combo.currentIndexChanged.connect(
            lambda *_: self._update_advisor_hydra_availability()
        )
        self.trigger_edit.textChanged.connect(self._on_trigger_for_advisor)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_split)
        splitter.addWidget(self._right_tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter)
        self.setLayout(root)

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
        if self._lycoris_process is not None:
            self._lycoris_process.terminate()
        else:
            model_id = self.model_selector.currentData()
            if model_id == "animegan_v2":
                GanWrapper.cancel_process()
            else:
                LoRATuner.cancel_process()
        self.cancel_btn.setEnabled(False)
        self.handle_status_update("Cancellation requested...")

    # --- Config Methods ---
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

        dialog = TrainingReportCardDialog(card, run_dir=worker.run_dir, parent=self)
        dialog.start_tournament_requested.connect(self._open_checkpoint_tournament)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()
        self._report_card_dialog = dialog

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
        refusal = try_admit("lora-train")
        if refusal:
            self.training_finished_signal.emit("error", refusal, "")
            return
        run_dir = None
        try:
            run_dir = self._create_run_record(
                params, data_dir, model_id, rank, prompt, output_name, engine, trigger,
            )
            self._run_training_admitted(
                params, data_dir, model_id, rank, prompt, output_name, engine, trigger,
                run_dir=run_dir,
            )
        finally:
            gpu_lease.release("lora-train")

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
        (backend/src/pipeline/anime_training_pipeline.py) via this
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
            "backend.controllers.hydra_dispatch",
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
        from gui.src.helpers.worker_retention import retain_until_stopped
        retain_until_stopped(worker, worker.cleanup_unclaimed)

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

    # --- Dataset advisor (#744) ---

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

    def disposal_ready(self) -> bool:
        return not self._training_running()

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

