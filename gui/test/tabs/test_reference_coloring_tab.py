import pytest
from editor import LayerStack

from cel_shaded_generator_gui.tabs.reference_coloring_tab import ReferenceColoringTab

pytestmark = pytest.mark.gui


def test_initial_state_has_no_canvas(q_app):
    tab = ReferenceColoringTab()
    assert tab.canvas().layer_stack() is None
    assert "No canvas" in tab._status.text()


def test_binding_a_layer_stack_wires_canvas_and_panel(q_app):
    tab = ReferenceColoringTab()
    stack = LayerStack(8, 6)
    stack.add_layer("layer-1", "Layer 1")
    tab._canvas.set_layer_stack(stack)
    tab._layer_panel.set_layer_stack(stack)
    tab._update_status()
    assert tab.canvas().layer_stack() is stack
    assert tab.layer_panel().layer_stack() is stack
    assert "8x6" in tab._status.text()
    assert "1 layer" in tab._status.text()


def test_layer_panel_mutation_refreshes_canvas_and_status(q_app):
    tab = ReferenceColoringTab()
    stack = LayerStack(4, 4)
    tab._canvas.set_layer_stack(stack)
    tab._layer_panel.set_layer_stack(stack)
    tab._layer_panel._add_layer()
    assert len(stack.layers()) == 1
    assert "1 layer" in tab._status.text()


def test_default_tool_is_pan(q_app):
    tab = ReferenceColoringTab()
    assert tab.canvas().tool() == "pan"


def test_selecting_brush_radio_switches_canvas_tool(q_app):
    tab = ReferenceColoringTab()
    tab._brush_tool.setChecked(True)
    assert tab.canvas().tool() == "brush"
    tab._pan_tool.setChecked(True)
    assert tab.canvas().tool() == "pan"


def test_brush_radius_spin_updates_canvas(q_app):
    tab = ReferenceColoringTab()
    tab._brush_radius_spin.setValue(12)
    assert tab.canvas().brush_radius() == 12


def test_layer_selection_wires_canvas_active_layer(q_app):
    tab = ReferenceColoringTab()
    stack = LayerStack(4, 4)
    stack.add_layer("only", "Only")
    tab._canvas.set_layer_stack(stack)
    tab._layer_panel.set_layer_stack(stack)
    tab._layer_panel.select_layer("only")
    assert tab.canvas().active_layer_id() == "only"


def test_new_canvas_default_layer_is_selected_and_paintable(q_app, monkeypatch):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (10, True)))
    tab = ReferenceColoringTab()
    tab._new_canvas()
    assert tab.canvas().active_layer_id() == "layer-1"
    tab._canvas.set_brush_color((255, 0, 0, 255))
    tab._canvas.set_brush_radius(0)
    tab._canvas._paint_dot_at_pixel(5, 5)
    assert tab.canvas().layer_stack().layer("layer-1").pixels[5, 5].tolist() == [255, 0, 0, 255]


def _new_canvas(tab, monkeypatch, size=10):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (size, True)))
    tab._new_canvas()


def test_new_canvas_creates_a_history_bound_to_both_widgets(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    assert tab.history() is not None
    assert tab.canvas()._history is tab.history()
    assert tab.layer_panel()._history is tab.history()


def test_undo_button_reverts_a_layer_addition_and_refreshes_ui(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    tab._layer_panel._add_layer()
    assert len(tab.canvas().layer_stack().layers()) == 2
    tab._undo()
    assert len(tab.canvas().layer_stack().layers()) == 1
    assert "1 layer" in tab._status.text()


def test_redo_button_reapplies_an_undone_mutation(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    tab._layer_panel._add_layer()
    tab._undo()
    tab._redo()
    assert len(tab.canvas().layer_stack().layers()) == 2


def test_undo_before_any_canvas_exists_is_a_no_op(q_app):
    tab = ReferenceColoringTab()
    tab._undo()
    tab._redo()
    assert tab.history() is None


def test_edit_mask_checkbox_toggles_canvas_mask_mode(q_app):
    tab = ReferenceColoringTab()
    assert tab.canvas().mask_mode() is False
    tab._edit_mask_checkbox.setChecked(True)
    assert tab.canvas().mask_mode() is True
    tab._edit_mask_checkbox.setChecked(False)
    assert tab.canvas().mask_mode() is False


def test_mask_value_spin_updates_canvas_intensity(q_app):
    tab = ReferenceColoringTab()
    tab._mask_value_spin.setValue(64)
    assert tab.canvas().mask_intensity() == 64


def test_layer_panels_mask_buttons_reach_the_bound_layer_stack(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    tab.layer_panel()._add_mask_to_selected_layer()
    assert tab.canvas().layer_stack().layer("layer-1").mask is not None
    assert "1 layer" in tab._status.text()


def _paint_ring(tab, monkeypatch, size=10):
    _new_canvas(tab, monkeypatch, size=size)
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[2, 2:8, :] = [0, 0, 0, 255]
    layer.pixels[7, 2:8, :] = [0, 0, 0, 255]
    layer.pixels[2:8, 2, :] = [0, 0, 0, 255]
    layer.pixels[2:8, 7, :] = [0, 0, 0, 255]


def test_segment_regions_button_adds_a_region_layer(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _paint_ring(tab, monkeypatch)
    tab._segment_regions()
    layer_stack = tab.canvas().layer_stack()
    assert len(layer_stack.layers()) == 2
    assert "2 layer" in tab._status.text()
    assert tab.layer_panel()._list.count() == 2


def test_segment_regions_button_records_history(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _paint_ring(tab, monkeypatch)
    tab._segment_regions()
    assert len(tab.canvas().layer_stack().layers()) == 2
    tab._undo()
    assert len(tab.canvas().layer_stack().layers()) == 1


def test_segment_regions_button_without_a_canvas_is_a_no_op(q_app):
    tab = ReferenceColoringTab()
    tab._segment_regions()
    assert tab.history() is None


def test_close_line_gaps_button_bridges_a_gap_and_enables_segmentation(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _paint_ring(tab, monkeypatch)
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[2, 4, :] = [0, 0, 0, 0]  # punch a 1px gap
    tab._segment_regions()
    assert len(tab.canvas().layer_stack().layers()) == 1  # leaks to the border, no region

    tab._max_gap_spin.setValue(1)
    tab._close_line_gaps()
    assert layer.pixels[2, 4, 3] == 255

    tab._segment_regions()
    assert len(tab.canvas().layer_stack().layers()) == 2


def _write_bible(tmp_path, accent=None):
    from colorization.style_bible import (
        CharacterStyleBible,
        MaterialPalette,
        StyleMaterial,
        save_style_bible,
    )

    bible = CharacterStyleBible(
        "aiko",
        "Aiko",
        "TV cel",
        [
            StyleMaterial(
                "hair", "Hair", MaterialPalette("#332233", "#665566", "#110F18", accent)
            ),
            StyleMaterial("skin", "Skin", MaterialPalette("#EEDDCC", "#FFEEDD", "#AA8866")),
        ],
    )
    path = tmp_path / "aiko.json"
    save_style_bible(path, bible)
    return path


def _bind_bible(tab, monkeypatch, tmp_path, accent=None):
    from PySide6.QtWidgets import QFileDialog

    path = _write_bible(tmp_path, accent=accent)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), ""))
    )
    tab._bind_style_bible()


def test_bind_style_bible_populates_material_and_role_combos(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _bind_bible(tab, monkeypatch, tmp_path)
    assert tab.style_bible() is not None
    assert tab._material_combo.count() == 2
    assert [tab._role_combo.itemText(i) for i in range(tab._role_combo.count())] == [
        "local",
        "light",
        "shadow",
    ]


def test_bind_style_bible_role_combo_includes_accent_when_present(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _bind_bible(tab, monkeypatch, tmp_path, accent="#FF00FF")
    assert "accent" in [tab._role_combo.itemText(i) for i in range(tab._role_combo.count())]


def test_bind_style_bible_cancelled_dialog_is_a_no_op(q_app, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    tab = ReferenceColoringTab()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: ("", "")))
    tab._bind_style_bible()
    assert tab.style_bible() is None


def test_apply_palette_color_recolors_selected_layer(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._role_combo.setCurrentText("light")
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[0, 0] = [1, 2, 3, 255]

    tab._apply_palette_color()

    assert layer.pixels[0, 0].tolist() == [0x66, 0x55, 0x66, 255]


def test_apply_palette_color_records_history(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._material_combo.setCurrentIndex(0)
    tab._role_combo.setCurrentText("light")
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[0, 0] = [1, 2, 3, 255]

    tab._apply_palette_color()
    assert layer.pixels[0, 0, :3].tolist() == [0x66, 0x55, 0x66]
    tab._undo()
    assert tab.canvas().layer_stack().layer("layer-1").pixels[0, 0, :3].tolist() == [1, 2, 3]


def test_apply_palette_color_without_a_bible_is_a_no_op(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[0, 0] = [1, 2, 3, 255]
    tab._apply_palette_color()
    assert layer.pixels[0, 0].tolist() == [1, 2, 3, 255]
