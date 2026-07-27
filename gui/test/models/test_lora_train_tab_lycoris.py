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

from gui.src.tabs.models.delta.lora_train_tab import LoRATrainTab, _TRAINING_ENGINES

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
        )

    args, kwargs = mock_popen.call_args
    cmd = args[0]
    assert cmd[:3] == [sys.executable, "-m", "backend.dispatcher"]
    assert "command=train" in cmd
    assert f"training=lycoris_{engine}" in cmd
    assert "model.model_id=OnomaAIResearch/Illustrious-XL-v2.0" in cmd
    assert "data.images_dir=/data/my_char" in cmd
    assert "data.trigger_word=mychar_xyz" in cmd
    assert "output_dir=my_char_lora" in cmd
    assert tab._lycoris_process is None  # cleared in finally after wait() returns


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
