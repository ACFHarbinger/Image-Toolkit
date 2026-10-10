import pytest
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
)

from gui.src.classes.base.base_generative_tab import (
    CONFIG_SCHEMA_KEY,
    CONFIG_SCHEMA_VERSION,
    BaseGenerativeTab,
    model_choice_label,
)

pytestmark = pytest.mark.gui


@pytest.fixture
def gen_tab(q_app):
    tab = BaseGenerativeTab()
    layout = QFormLayout()
    tab.setLayout(layout)
    return tab


def test_add_param_widget(gen_tab):
    layout = gen_tab.layout()
    widget = QLineEdit()
    gen_tab.add_param_widget(layout, "Label", widget, "test_param")

    assert "test_param" in gen_tab.widgets
    assert gen_tab.widgets["test_param"] == widget
    assert layout.rowCount() > 0


def test_collect_values(gen_tab):
    layout = gen_tab.layout()

    combo = QComboBox()
    combo.addItem("Friendly A", "id-a")
    combo.addItem("Friendly B", "id-b")
    gen_tab.add_param_widget(layout, "Combo", combo, "p_combo")

    check = QCheckBox()
    check.setChecked(True)
    gen_tab.add_param_widget(layout, "Check", check, "p_check")

    spin = QSpinBox()
    spin.setValue(42)
    gen_tab.add_param_widget(layout, "Spin", spin, "p_spin")

    line = QLineEdit()
    line.setText("Hello")
    gen_tab.add_param_widget(layout, "Line", line, "p_line")

    params = gen_tab.collect()

    assert params[CONFIG_SCHEMA_KEY] == CONFIG_SCHEMA_VERSION
    assert params["p_combo"] == "id-a"
    assert params["p_check"] is True
    assert params["p_spin"] == 42
    assert params["p_line"] == "Hello"


def test_collect_combo_without_item_data_uses_text(gen_tab):
    combo = QComboBox()
    combo.addItems(["A", "B"])
    gen_tab.add_param_widget(gen_tab.layout(), "Combo", combo, "p_combo")
    combo.setCurrentIndex(1)

    assert gen_tab.collect()["p_combo"] == "B"


def test_set_config(gen_tab):
    layout = gen_tab.layout()

    spin = QSpinBox()
    spin.setRange(0, 1000)
    gen_tab.add_param_widget(layout, "Spin", spin, "p_spin")

    line = QLineEdit()
    gen_tab.add_param_widget(layout, "Line", line, "p_line")

    config = {"p_spin": 100, "p_line": "New Value", "unknown_param": "ignore me"}

    gen_tab.set_config(config)

    assert spin.value() == 100
    assert line.text() == "New Value"


def test_set_config_restores_combo_by_id_after_label_rename(gen_tab):
    combo = QComboBox()
    combo.addItem("Old Friendly", "stable-id")
    combo.addItem("Other", "other-id")
    gen_tab.add_param_widget(gen_tab.layout(), "Combo", combo, "p_combo")
    combo.setCurrentIndex(1)

    snapshot = gen_tab.collect()
    assert snapshot["p_combo"] == "other-id"

    combo.setItemText(1, "Renamed Friendly")
    combo.setCurrentIndex(0)
    gen_tab.set_config(snapshot)

    assert combo.currentData() == "other-id"
    assert gen_tab.config_migration_note is None


def test_set_config_migrates_legacy_combo_label(gen_tab):
    combo = QComboBox()
    combo.addItem("Standard (LoRA)", "standard")
    combo.addItem("LyCORIS: LoCon", "locon")
    gen_tab.add_param_widget(gen_tab.layout(), "Engine", combo, "engine")

    gen_tab.set_config({"engine": "LyCORIS: LoCon"})

    assert combo.currentData() == "locon"
    assert gen_tab.config_migration_note is None


def test_set_config_unknown_combo_id_keeps_current_and_shows_note(gen_tab):
    combo = QComboBox()
    combo.addItem("Engine A", "a")
    combo.addItem("Engine B", "b")
    gen_tab.add_param_widget(gen_tab.layout(), "Combo", combo, "p_combo")
    combo.setCurrentIndex(1)

    gen_tab.set_config({"p_combo": "Engine A Renamed"})

    assert combo.currentData() == "b"
    assert combo.currentIndex() == 1
    assert gen_tab.config_migration_note is not None
    assert "Engine A Renamed" in gen_tab.config_migration_note
    assert gen_tab._migration_label is not None
    assert not gen_tab._migration_label.isHidden()
    assert "Engine A Renamed" in gen_tab._migration_label.text()


class TestModelChoiceLabel:
    """#728: friendly combo labels must show what they resolve to."""

    def test_appends_id_when_label_hides_it(self):
        label = model_choice_label(
            "Illustrious XL V2.0 (Base SDXL)",
            "stabilityai/stable-diffusion-xl-base-1.0",
        )
        assert label == (
            "Illustrious XL V2.0 (Base SDXL) · "
            "stabilityai/stable-diffusion-xl-base-1.0"
        )

    def test_identical_ids_stay_visible_for_comparison(self):
        # Both Illustrious rows resolve to the same base id — the append
        # makes the mismatch visible in the dropdown.
        a = model_choice_label(
            "Illustrious XL V2.0 (Base SDXL)",
            "stabilityai/stable-diffusion-xl-base-1.0",
        )
        b = model_choice_label(
            "Illustrious Lumina (Base SDXL)",
            "stabilityai/stable-diffusion-xl-base-1.0",
        )
        assert a != b
        assert a.endswith("stabilityai/stable-diffusion-xl-base-1.0")
        assert b.endswith("stabilityai/stable-diffusion-xl-base-1.0")

    @pytest.mark.parametrize(
        "label,model_id",
        [
            ("AnimeGANv2", "animegan_v2"),
            ("Anything V3", "ckpt/anything-v3.0"),
            ("Animagine XL 3.1", "cagliostrolab/animagine-xl-3.1"),
        ],
    )
    def test_recognizable_labels_stay_untouched(self, label, model_id):
        assert model_choice_label(label, model_id) == label
