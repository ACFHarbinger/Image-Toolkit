"""Content Gen §1.3: LyCORIS variants (LoCon/LoHa/LoKr) GUI wiring.

Covers the Training Engine dropdown added to LoRATrainTab and the
subprocess-based dispatch to anime_training_pipeline.py for the three
LyCORIS options, without spawning a real training process.

Note: LoRATrainTab.__init__ connects training_finished_signal to
handle_training_finished, which shows a *blocking* QMessageBox. In real
usage that's fine (it runs after a background thread's work is done, on
the main/GUI thread, waiting for the user to click OK) -- but calling
_run_lycoris_training() directly from a test (same thread, no user to
click anything) means that modal would hang the test forever. Every test
below patches QMessageBox so it never actually blocks.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from gui.src.tabs.models.delta.lora_train_tab import _TRAINING_ENGINES, LoRATrainTab

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _no_modal_dialogs():
    with patch("gui.src.tabs.models.delta.lora_train_tab.QMessageBox"):
        yield


@pytest.fixture
def tab():
    return LoRATrainTab()


def test_engine_combo_defaults_to_standard(tab):
    assert tab.engine_combo.currentData() == "standard"
    assert tab.engine_combo.currentText() == "Standard (LoRA)"


def test_engine_combo_has_all_lycoris_variants(tab):
    ids = [tab.engine_combo.itemData(i) for i in range(tab.engine_combo.count())]
    assert ids == ["standard", "locon", "loha", "lokr"]
    assert len(_TRAINING_ENGINES) == 4


def test_standard_engine_uses_legacy_lora_tuner_path(tab):
    """engine='standard' must never touch _run_lycoris_training."""
    with patch.object(tab, "_run_lycoris_training") as mock_lycoris, \
         patch("gui.src.tabs.models.delta.lora_train_tab.LoRATuner") as mock_tuner:
        mock_tuner.is_cancelled = False
        instance = mock_tuner.return_value
        instance.train.return_value = None
        tab.run_training(
            params={}, data_dir="/tmp/data", model_id="some/model",
            rank=4, prompt="trigger", output_name="out", engine="standard",
        )
        mock_lycoris.assert_not_called()
        mock_tuner.assert_called_once_with(model_id="some/model", output_dir="out")


def test_lycoris_engine_forwards_form_controls(tab):
    """#726: run_training must forward the visible epochs/batch/LR/rank
    controls into the LyCORIS launcher."""
    with patch.object(tab, "_run_lycoris_training") as mock_lycoris:
        tab.run_training(
            params={"epochs": 9, "batch_size": 2, "learning_rate": 2e-4},
            data_dir="/tmp/data", model_id="some/model",
            rank=16, prompt="trigger", output_name="out", engine="loha",
        )
    mock_lycoris.assert_called_once_with(
        "/tmp/data", "some/model", "trigger", "out", "loha",
        epochs=9, batch_size=2, learning_rate=2e-4, rank=16,
    )


@pytest.mark.parametrize("engine", ["locon", "loha", "lokr"])
def test_lycoris_engine_builds_correct_dispatcher_command(tab, engine):
    fake_proc = MagicMock()
    fake_proc.stdout = iter(["line one\n", "line two\n"])
    fake_proc.wait.return_value = 0

    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.subprocess.Popen",
        return_value=fake_proc,
    ) as mock_popen:
        tab._run_lycoris_training(
            data_dir="/data/my_char",
            model_id="OnomaAIResearch/Illustrious-XL-v2.0",
            prompt="mychar_xyz",
            output_name="my_char_lora",
            engine=engine,
            epochs=7,
            batch_size=3,
            learning_rate=5e-5,
            rank=32,
        )

    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert cmd[:3] == [sys.executable, "-m", "backend.controllers.hydra_dispatch"]
    assert "command=train" in cmd
    assert f"training=lycoris_{engine}" in cmd
    assert "model.model_id=OnomaAIResearch/Illustrious-XL-v2.0" in cmd
    assert "data.images_dir=/data/my_char" in cmd
    assert "data.trigger_word=mychar_xyz" in cmd
    assert "output_dir=my_char_lora" in cmd
    # #726: the four visible controls must reach the Hydra command
    assert "training.rank=32" in cmd
    assert "training.train_batch_size=3" in cmd
    assert "training.max_train_epochs=7" in cmd
    assert "optimizer.unet_lr=5e-05" in cmd
    assert tab._lycoris_process is None  # cleared in finally after wait() returns


def test_lycoris_command_uses_form_defaults(tab):
    """Omitting the controls falls back to the form's own defaults."""
    fake_proc = MagicMock()
    fake_proc.stdout = iter([])
    fake_proc.wait.return_value = 0

    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.subprocess.Popen",
        return_value=fake_proc,
    ) as mock_popen:
        tab._run_lycoris_training("/d", "m", "p", "o", "locon")

    cmd = mock_popen.call_args.args[0]
    assert "training.rank=4" in cmd
    assert "training.train_batch_size=1" in cmd
    assert "training.max_train_epochs=5" in cmd
    assert "optimizer.unet_lr=0.0001" in cmd


def test_lycoris_training_success_emits_success_signal(tab):
    fake_proc = MagicMock()
    fake_proc.stdout = iter([])
    fake_proc.wait.return_value = 0
    signals = []
    tab.training_finished_signal.connect(lambda *a: signals.append(a))

    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.subprocess.Popen",
        return_value=fake_proc,
    ):
        tab._run_lycoris_training("/d", "m", "p", "o", "locon")

    assert signals == [("success", "LyCORIS training finished and weights saved.")]


def test_lycoris_training_nonzero_exit_emits_error_signal(tab):
    fake_proc = MagicMock()
    fake_proc.stdout = iter([])
    fake_proc.wait.return_value = 1
    signals = []
    tab.training_finished_signal.connect(lambda *a: signals.append(a))

    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.subprocess.Popen",
        return_value=fake_proc,
    ):
        tab._run_lycoris_training("/d", "m", "p", "o", "loha")

    assert signals[0][0] == "error"


def test_lycoris_training_negative_returncode_is_treated_as_cancel(tab):
    """A negative returncode means the process was killed by a signal --
    i.e. cancel_training()'s proc.terminate() call, not a real failure."""
    fake_proc = MagicMock()
    fake_proc.stdout = iter([])
    fake_proc.wait.return_value = -15  # SIGTERM
    signals = []
    tab.training_finished_signal.connect(lambda *a: signals.append(a))

    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.subprocess.Popen",
        return_value=fake_proc,
    ):
        tab._run_lycoris_training("/d", "m", "p", "o", "lokr")

    assert signals[0][0] == "cancel"


def test_cancel_training_terminates_lycoris_subprocess_when_active(tab):
    fake_proc = MagicMock()
    tab._lycoris_process = fake_proc
    tab.cancel_training()
    fake_proc.terminate.assert_called_once()


def test_collect_persists_model_and_engine_ids_not_labels(tab):
    tab.model_selector.setCurrentIndex(0)
    tab.engine_combo.setCurrentIndex(2)
    data = tab.collect()
    assert data["config_schema"] == 2
    assert data["model_id"] == "stabilityai/stable-diffusion-xl-base-1.0"
    assert data["engine"] == "loha"
    assert data["model_id"] != tab.model_selector.currentText()
    assert data["engine"] != tab.engine_combo.currentText()


def test_set_config_restores_engine_by_id_after_label_rename(tab):
    tab.engine_combo.setCurrentIndex(3)
    snapshot = tab.collect()
    tab.engine_combo.setItemText(3, "LyCORIS: LoKr (renamed)")
    tab.engine_combo.setCurrentIndex(0)

    tab.set_config(snapshot)

    assert tab.engine_combo.currentData() == "lokr"
    assert tab.config_migration_note is None


def test_set_config_migrates_legacy_engine_label(tab):
    tab.set_config({"engine": "LyCORIS: LoHa (small datasets)"})
    assert tab.engine_combo.currentData() == "loha"


def test_set_config_unknown_engine_keeps_current(tab):
    tab.engine_combo.setCurrentIndex(2)
    tab.set_config({"engine": "lycoris-that-was-removed"})
    assert tab.engine_combo.currentData() == "loha"
    assert tab.config_migration_note is not None
    assert "lycoris-that-was-removed" in tab.config_migration_note


def test_model_combo_shows_resolved_id(tab):
    """#728: the two Illustrious rows must visibly share the SDXL base id."""
    texts = [tab.model_selector.itemText(i) for i in range(tab.model_selector.count())]
    assert (
        "Illustrious XL V2.0 (Base SDXL) · stabilityai/stable-diffusion-xl-base-1.0"
        in texts
    )
    assert (
        "Illustrious Lumina (Base SDXL) · stabilityai/stable-diffusion-xl-base-1.0"
        in texts
    )
    # itemData is unchanged — only the display text grows.
    assert tab.model_selector.itemData(0) == "stabilityai/stable-diffusion-xl-base-1.0"


def test_start_training_thread_forwards_dedicated_trigger(tab):
    tab.trigger_edit.setText("my_char")
    tab.prompt_edit.setText("1girl, style")
    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.threading.Thread"
    ) as mock_thread:
        mock_thread.return_value.start = MagicMock()
        tab.start_training_thread()
    kwargs = mock_thread.call_args.kwargs["kwargs"]
    assert kwargs["trigger"] == "my_char"
    assert kwargs["prompt"] == "1girl, style"


def test_standard_engine_prepends_trigger_to_instance_prompt(tab):
    with patch.object(tab, "_run_lycoris_training") as mock_lycoris, \
         patch("gui.src.tabs.models.delta.lora_train_tab.LoRATuner") as mock_tuner:
        mock_tuner.is_cancelled = False
        instance = mock_tuner.return_value
        instance.train.return_value = None
        tab.run_training(
            params={}, data_dir="/tmp/data", model_id="some/model",
            rank=4, prompt="1girl, style", trigger="my_char",
            output_name="out", engine="standard",
        )
        mock_lycoris.assert_not_called()
        assert instance.train.call_args.kwargs["instance_prompt"] == "my_char, 1girl, style"


def test_lycoris_run_training_uses_dedicated_trigger_not_prompt(tab):
    with patch.object(tab, "_run_lycoris_training") as mock_lycoris:
        tab.run_training(
            params={"epochs": 9, "batch_size": 2, "learning_rate": 2e-4},
            data_dir="/tmp/data", model_id="some/model",
            rank=16, prompt="1girl, style of my_char", trigger="my_char",
            output_name="out", engine="loha",
        )
    mock_lycoris.assert_called_once_with(
        "/tmp/data", "some/model", "my_char", "out", "loha",
        epochs=9, batch_size=2, learning_rate=2e-4, rank=16,
    )


def test_lycoris_command_uses_dedicated_trigger_word(tab):
    fake_proc = MagicMock()
    fake_proc.stdout = iter([])
    fake_proc.wait.return_value = 0

    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.subprocess.Popen",
        return_value=fake_proc,
    ) as mock_popen:
        tab.run_training(
            params={},
            data_dir="/data/my_char",
            model_id="some/model",
            rank=4,
            prompt="1girl, style of my_char",
            trigger="mychar_xyz",
            output_name="out",
            engine="locon",
        )

    cmd = mock_popen.call_args.args[0]
    assert "data.trigger_word=mychar_xyz" in cmd
    assert "data.trigger_word=1girl, style of my_char" not in cmd


def test_browse_dataset_uses_non_native_dialog(tab):
    from PySide6.QtWidgets import QFileDialog

    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.QFileDialog.getExistingDirectory",
        return_value="",
    ) as mock_dialog:
        tab.browse_dataset()
    assert (
        mock_dialog.call_args.args[3] == QFileDialog.Option.DontUseNativeDialog
    )
