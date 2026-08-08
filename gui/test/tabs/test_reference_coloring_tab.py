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


def test_duplicate_selected_layer_copies_pixels_and_selects_copy(q_app):
    tab = ReferenceColoringTab()
    stack = LayerStack(2, 2)
    source = stack.add_layer("source", "Source")
    source.pixels[0, 1] = [1, 2, 3, 255]
    stack.add_mask("source")
    source.mask[0, 1] = 77
    tab._canvas.set_layer_stack(stack)
    tab._layer_panel.set_layer_stack(stack)
    tab._layer_panel.set_history(None)
    tab._layer_panel.select_layer("source")

    tab._layer_panel._duplicate_selected_layer()

    duplicate = stack.layers()[-1]
    assert duplicate.meta.name == "Source copy"
    assert duplicate.pixels[0, 1].tolist() == [1, 2, 3, 255]
    assert duplicate.mask[0, 1] == 77
    assert tab._layer_panel.selected_layer_id() == duplicate.meta.id


def test_default_tool_is_pan(q_app):
    tab = ReferenceColoringTab()
    assert tab.canvas().tool() == "pan"


def test_selecting_brush_radio_switches_canvas_tool(q_app):
    tab = ReferenceColoringTab()
    tab._brush_tool.setChecked(True)
    assert tab.canvas().tool() == "brush"
    tab._pan_tool.setChecked(True)
    assert tab.canvas().tool() == "pan"


def test_selecting_eraser_radio_switches_canvas_tool(q_app):
    tab = ReferenceColoringTab()
    tab._eraser_tool.setChecked(True)
    assert tab.canvas().tool() == "eraser"
    tab._pan_tool.setChecked(True)
    assert tab.canvas().tool() == "pan"


def test_eraser_tool_erases_via_the_tab(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[:, :] = [1, 2, 3, 255]
    tab._eraser_tool.setChecked(True)
    tab._brush_radius_spin.setValue(1)
    tab._canvas._paint_dot_at_pixel(5, 5)
    assert layer.pixels[5, 5, 3] == 0


def test_brush_radius_spin_updates_canvas(q_app):
    tab = ReferenceColoringTab()
    tab._brush_radius_spin.setValue(12)
    assert tab.canvas().brush_radius() == 12


def test_brush_hardness_spin_defaults_to_fully_hard_and_updates_canvas(q_app):
    tab = ReferenceColoringTab()
    assert tab.canvas().brush_hardness() == 1.0
    tab._brush_hardness_spin.setValue(0.3)
    assert tab.canvas().brush_hardness() == 0.3


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


def _add_touching_region_layers(tab):
    stack = tab.canvas().layer_stack()
    a = stack.add_layer("layer-1-region-1", "Region 1")
    a.pixels[:, :3, 3] = 255
    b = stack.add_layer("layer-1-region-2", "Region 2")
    b.pixels[:, 3:, 3] = 255
    tab._region_layer_ids = ["layer-1-region-1", "layer-1-region-2"]
    tab._layer_panel.refresh()


def test_assign_correspondence_records_entry(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._role_combo.setCurrentText("local")

    tab._assign_correspondence()

    correspondence_set = tab.correspondence_set()
    assert correspondence_set is not None
    assert len(correspondence_set.correspondences) == 1
    assert correspondence_set.correspondences[0].region_id == "layer-1-region-1"
    assert correspondence_set.correspondences[0].material_id == "hair"


def test_assign_correspondence_reports_conflicting_assignment(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._assign_correspondence()

    tab._material_combo.setCurrentIndex(1)  # skin
    tab._assign_correspondence()

    assert len(tab.correspondence_set().correspondences) == 1
    assert "competing" in tab._status.text()


def test_assign_correspondence_without_bible_is_a_no_op(q_app, monkeypatch):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._assign_correspondence()
    assert tab.correspondence_set() is None


def _bind_bible_skin_first(tab, monkeypatch, tmp_path):
    from colorization.style_bible import (
        CharacterStyleBible,
        MaterialPalette,
        StyleMaterial,
        save_style_bible,
    )
    from PySide6.QtWidgets import QFileDialog

    bible = CharacterStyleBible(
        "aiko",
        "Aiko",
        "TV cel",
        [
            StyleMaterial("skin", "Skin", MaterialPalette("#EEDDCC", "#FFEEDD", "#AA8866")),
            StyleMaterial("hair", "Hair", MaterialPalette("#332233", "#665566", "#110F18")),
        ],
    )
    path = tmp_path / "aiko.json"
    save_style_bible(path, bible)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(path), ""))
    )
    tab._bind_style_bible()


def test_suggest_material_selects_top_ranked_candidate_from_adjacency(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible_skin_first(tab, monkeypatch, tmp_path)
    tab._layer_panel.select_layer("layer-1-region-1")
    hair_index = tab._material_combo.findData("hair")
    tab._material_combo.setCurrentIndex(hair_index)
    tab._assign_correspondence()

    # Without adjacency, ties break to list order (skin first); confirm
    # the assigned neighbor's material ("hair") wins the suggestion instead.
    tab._layer_panel.select_layer("layer-1-region-2")
    tab._suggest_material()

    assert tab._material_combo.currentData() == "hair"
    assert "Suggested 'hair'" in tab._status.text()


def test_suggest_material_without_canvas_is_a_no_op(q_app):
    tab = ReferenceColoringTab()
    tab._suggest_material()
    assert tab.correspondence_set() is None


def _stub_existing_directory(monkeypatch, path):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(path))
    )


def test_save_document_writes_canvas_to_directory(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[0, 0] = [9, 8, 7, 255]
    _stub_existing_directory(monkeypatch, tmp_path)

    tab._save_document()

    assert (tmp_path / "manifest.json").exists()
    assert "Saved document" in tab._status.text()


def test_export_png_writes_flattened_rgba_composite(q_app, monkeypatch, tmp_path):
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QFileDialog

    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch, size=2)
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[0, 0] = [10, 20, 30, 255]
    destination = tmp_path / "composite.png"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(destination), "")),
    )

    tab._export_png()

    image = QImage(str(destination)).convertToFormat(QImage.Format.Format_RGBA8888)
    assert image.size().width() == 2
    assert image.size().height() == 2
    assert image.pixelColor(0, 0).getRgb() == (10, 20, 30, 255)
    assert "Exported composite PNG" in tab._status.text()


def test_export_png_without_canvas_is_a_no_op(q_app, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    called = False

    def fail_if_called(*_args, **_kwargs):
        nonlocal called
        called = True
        return ("", "")

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(fail_if_called))
    tab = ReferenceColoringTab()
    tab._export_png()
    assert not called
    assert "No canvas" in tab._status.text()


def test_import_image_layer_preserves_rgba_and_is_undoable(q_app, monkeypatch, tmp_path):
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QFileDialog

    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch, size=2)
    source = tmp_path / "reference.png"
    image = QImage(2, 2, QImage.Format.Format_RGBA8888)
    image.fill(QColor(0, 0, 0, 0))
    image.setPixelColor(1, 0, QColor(10, 20, 30, 128))
    assert image.save(str(source), "PNG")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(source), "")),
    )

    tab._import_image_layer()

    layer = tab.canvas().layer_stack().layers()[-1]
    assert layer.meta.name == "reference"
    assert layer.pixels[0, 1].tolist() == [10, 20, 30, 128]
    assert tab.canvas().active_layer_id() == layer.meta.id
    tab._undo()
    assert len(tab.canvas().layer_stack().layers()) == 1


def test_import_image_layer_rejects_dimension_mismatch(q_app, monkeypatch, tmp_path):
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QFileDialog

    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch, size=2)
    source = tmp_path / "wrong.png"
    assert QImage(3, 2, QImage.Format.Format_RGBA8888).save(str(source), "PNG")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: (str(source), "")),
    )

    tab._import_image_layer()

    assert len(tab.canvas().layer_stack().layers()) == 1
    assert "dimensions must match" in tab._status.text()


def test_save_document_without_canvas_is_a_no_op(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, tmp_path)
    tab._save_document()
    assert not (tmp_path / "manifest.json").exists()


def test_open_document_restores_canvas_and_resets_history(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[2, 3] = [1, 2, 3, 255]
    _stub_existing_directory(monkeypatch, tmp_path)
    tab._save_document()

    fresh_tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, tmp_path)
    fresh_tab._open_document()

    loaded_layer = fresh_tab.canvas().layer_stack().layer("layer-1")
    assert loaded_layer.pixels[2, 3].tolist() == [1, 2, 3, 255]
    assert fresh_tab.history() is not None
    assert fresh_tab.canvas().active_layer_id() == "layer-1"


def test_open_document_reports_error_for_missing_manifest(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, tmp_path)
    tab._open_document()
    assert "Could not open document" in tab._status.text()


def test_save_then_open_document_round_trips_correspondence_and_regions(
    q_app, monkeypatch, tmp_path
):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path / "bibles")
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._assign_correspondence()

    document_dir = tmp_path / "doc"
    _stub_existing_directory(monkeypatch, document_dir)
    tab._save_document()

    fresh_tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, document_dir)
    fresh_tab._open_document()

    assert fresh_tab._region_layer_ids == ["layer-1-region-1", "layer-1-region-2"]
    correspondence_set = fresh_tab.correspondence_set()
    assert correspondence_set is not None
    assert correspondence_set.correspondences[0].region_id == "layer-1-region-1"
    assert correspondence_set.correspondences[0].material_id == "hair"


def _stub_text_input(monkeypatch, text):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (text, True)))


def test_new_project_creates_and_binds_a_bare_project(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, tmp_path)
    _stub_text_input(monkeypatch, "My Project")

    tab._new_project()

    assert tab.project_directory() == str(tmp_path)
    assert (tmp_path / "project.json").exists()
    assert "Created and bound project" in tab._status.text()


def test_new_project_cancelled_title_is_a_no_op(q_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QInputDialog

    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, tmp_path)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("", False)))

    tab._new_project()

    assert tab.project_directory() is None
    assert not (tmp_path / "project.json").exists()


def test_bind_project_requires_an_existing_manifest(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, tmp_path)

    tab._bind_project()

    assert tab.project_directory() is None
    assert "no project manifest" in tab._status.text()


def test_bind_project_binds_an_existing_project(q_app, monkeypatch, tmp_path):
    from project import create_project

    create_project(tmp_path, title="Existing")
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, tmp_path)

    tab._bind_project()

    assert tab.project_directory() == str(tmp_path)
    assert "Bound project" in tab._status.text()


def test_bind_style_bible_attaches_to_bound_project(q_app, monkeypatch, tmp_path):
    from project import create_project, load_project

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    create_project(project_dir, title="Existing")
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, project_dir)
    tab._bind_project()

    _bind_bible(tab, monkeypatch, tmp_path / "bibles")

    assert tab._bible_asset_path == "style-bibles/aiko.json"
    assert tab._bible_asset_path in load_project(project_dir).style_bible_assets


def test_suggest_and_assign_correspondence_use_project_learned_weights(
    q_app, monkeypatch, tmp_path
):
    from project import load_project

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    _bind_bible(tab, monkeypatch, tmp_path / "bibles")

    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._suggest_material()  # ranks via the project's SignalWeights, populates candidates
    tab._assign_correspondence()

    project = load_project(project_dir)
    assert project.correspondence_set_assets  # persisted into the project
    # Two ranked candidates (hair, skin) and a chosen id among them is
    # enough for one multiplicative-weights update, per
    # record_correspondence_choice's own no-op rule.
    assert project.signal_weights.update_count == 1

    tab._layer_panel.select_layer("layer-1-region-2")
    tab._material_combo.setCurrentIndex(1)  # skin
    tab._suggest_material()
    tab._assign_correspondence()

    updated_project = load_project(project_dir)
    assert updated_project.signal_weights.update_count == 2


def test_save_document_inside_bound_project_attaches_as_asset(q_app, monkeypatch, tmp_path):
    from project import load_project

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()

    document_dir = project_dir / "canvas" / "main"
    _stub_existing_directory(monkeypatch, document_dir)
    tab._save_document()

    assert "attached to bound project" in tab._status.text()
    assert load_project(project_dir).editor_document_assets == ["canvas/main"]


def test_save_document_outside_bound_project_is_not_attached(q_app, monkeypatch, tmp_path):
    from project import load_project

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()

    outside_dir = tmp_path / "outside"
    _stub_existing_directory(monkeypatch, outside_dir)
    tab._save_document()

    assert "attached to bound project" not in tab._status.text()
    assert load_project(project_dir).editor_document_assets == []


def test_save_document_without_bound_project_never_attaches(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _stub_existing_directory(monkeypatch, tmp_path / "doc")

    tab._save_document()

    assert "attached to bound project" not in tab._status.text()


def test_project_asset_combos_populate_after_save_and_bind_bible(q_app, monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    assert tab._project_document_combo.count() == 0
    assert tab._project_bible_combo.count() == 0

    document_dir = project_dir / "canvas" / "main"
    _stub_existing_directory(monkeypatch, document_dir)
    tab._save_document()
    assert [
        tab._project_document_combo.itemText(i) for i in range(tab._project_document_combo.count())
    ] == ["canvas/main"]

    _bind_bible(tab, monkeypatch, tmp_path / "bibles")
    assert tab._project_bible_combo.count() == 1
    assert tab._project_bible_combo.itemData(0) == "style-bibles/aiko.json"


def test_open_project_document_reopens_without_a_file_dialog(q_app, monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    layer = tab.canvas().layer_stack().layer("layer-1")
    layer.pixels[1, 1] = [9, 8, 7, 255]
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    document_dir = project_dir / "canvas" / "main"
    _stub_existing_directory(monkeypatch, document_dir)
    tab._save_document()

    fresh_tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, project_dir)
    fresh_tab._bind_project()
    fresh_tab._project_document_combo.setCurrentIndex(0)

    fresh_tab._open_project_document()

    assert fresh_tab.canvas().layer_stack().layer("layer-1").pixels[1, 1].tolist() == [
        9,
        8,
        7,
        255,
    ]


def test_open_project_document_without_selection_is_a_no_op(q_app):
    tab = ReferenceColoringTab()
    tab._open_project_document()
    assert tab.canvas().layer_stack() is None


def test_load_project_bible_loads_without_a_file_dialog(q_app, monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    _bind_bible(tab, monkeypatch, tmp_path / "bibles")

    fresh_tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, project_dir)
    fresh_tab._bind_project()
    fresh_tab._project_bible_combo.setCurrentIndex(0)

    fresh_tab._load_project_bible()

    assert fresh_tab.style_bible() is not None
    assert fresh_tab.style_bible().id == "aiko"
    assert fresh_tab._material_combo.count() == 2


def test_load_project_bible_without_selection_is_a_no_op(q_app):
    tab = ReferenceColoringTab()
    tab._load_project_bible()
    assert tab.style_bible() is None


def _stub_text_dialog(monkeypatch, text, accepted=True):
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog, "getText", staticmethod(lambda *a, **k: (text, accepted))
    )


def test_propagate_correspondence_extends_to_explicit_target(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._assign_correspondence()

    _stub_text_dialog(monkeypatch, "layer-1-region-2")
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._propagate_correspondence()

    correspondence_set = tab.correspondence_set()
    assert {item.region_id: item.material_id for item in correspondence_set.correspondences} == {
        "layer-1-region-1": "hair",
        "layer-1-region-2": "hair",
    }
    assert "Propagated to 1 region" in tab._status.text()


def test_propagate_correspondence_prefills_adjacency_suggested_targets(
    q_app, monkeypatch, tmp_path
):
    from PySide6.QtWidgets import QInputDialog

    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._assign_correspondence()

    seen_kwargs = {}

    def _fake_get_text(*args, **kwargs):
        seen_kwargs.update(kwargs)
        return ("", False)

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(_fake_get_text))
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._propagate_correspondence()

    assert seen_kwargs.get("text") == "layer-1-region-2"


def test_propagate_correspondence_without_existing_entry_is_a_no_op(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path)
    # Assign a different region so a correspondence set exists, but
    # layer-1-region-1 itself still has no entry to propagate.
    tab._layer_panel.select_layer("layer-1-region-2")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._assign_correspondence()
    tab._layer_panel.select_layer("layer-1-region-1")

    tab._propagate_correspondence()

    assert "no existing correspondence" in tab._status.text()


def test_propagate_correspondence_without_any_correspondence_set_is_a_no_op(
    q_app, monkeypatch, tmp_path
):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._layer_panel.select_layer("layer-1-region-1")

    tab._propagate_correspondence()

    assert tab.correspondence_set() is None


def test_propagate_correspondence_cancelled_dialog_is_a_no_op(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)
    tab._assign_correspondence()

    _stub_text_dialog(monkeypatch, "layer-1-region-2", accepted=False)
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._propagate_correspondence()

    assert len(tab.correspondence_set().correspondences) == 1


def test_propagate_correspondence_reports_conflicting_target(q_app, monkeypatch, tmp_path):
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _bind_bible(tab, monkeypatch, tmp_path)
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._assign_correspondence()
    tab._layer_panel.select_layer("layer-1-region-2")
    tab._material_combo.setCurrentIndex(1)  # skin
    tab._assign_correspondence()

    _stub_text_dialog(monkeypatch, "layer-1-region-2")
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._propagate_correspondence()

    assert len(tab.correspondence_set().correspondences) == 2
    assert "competing" in tab._status.text()


def test_propagate_correspondence_without_canvas_is_a_no_op(q_app):
    tab = ReferenceColoringTab()
    tab._propagate_correspondence()
    assert tab.correspondence_set() is None


def test_detach_project_document_removes_entry_without_deleting_files(
    q_app, monkeypatch, tmp_path
):
    from project import load_project

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    document_dir = project_dir / "canvas" / "main"
    _stub_existing_directory(monkeypatch, document_dir)
    tab._save_document()
    assert tab._project_document_combo.count() == 1

    tab._project_document_combo.setCurrentIndex(0)
    tab._detach_project_document()

    assert tab._project_document_combo.count() == 0
    assert load_project(project_dir).editor_document_assets == []
    assert (document_dir / "manifest.json").exists()  # files untouched
    assert "Detached document" in tab._status.text()


def test_detach_project_document_without_selection_is_a_no_op(q_app):
    tab = ReferenceColoringTab()
    tab._detach_project_document()
    assert tab._project_document_combo.count() == 0


def test_detach_project_bible_removes_entry_and_clears_active_asset_path(
    q_app, monkeypatch, tmp_path
):
    from project import load_project

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    _bind_bible(tab, monkeypatch, tmp_path / "bibles")
    assert tab._bible_asset_path == "style-bibles/aiko.json"
    bible_path = project_dir / "style-bibles" / "aiko.json"
    assert bible_path.exists()

    tab._project_bible_combo.setCurrentIndex(0)
    tab._detach_project_bible()

    assert tab._project_bible_combo.count() == 0
    assert load_project(project_dir).style_bible_assets == []
    assert bible_path.exists()  # file untouched
    assert tab._bible_asset_path is None
    assert "Detached bible" in tab._status.text()


def test_detach_project_bible_without_selection_is_a_no_op(q_app):
    tab = ReferenceColoringTab()
    tab._detach_project_bible()
    assert tab._project_bible_combo.count() == 0


def test_binding_a_project_loads_its_existing_correspondence_set(q_app, monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    _bind_bible(tab, monkeypatch, tmp_path / "bibles")
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)  # hair
    tab._assign_correspondence()
    assert tab.correspondence_set() is not None

    fresh_tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, project_dir)
    fresh_tab._bind_project()

    correspondence_set = fresh_tab.correspondence_set()
    assert correspondence_set is not None
    assert correspondence_set.correspondences[0].region_id == "layer-1-region-1"
    assert correspondence_set.correspondences[0].material_id == "hair"


def test_binding_a_project_without_a_correspondence_set_leaves_it_none(
    q_app, monkeypatch, tmp_path
):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    assert tab.correspondence_set() is None


def test_binding_a_different_project_clears_the_previous_correspondence_set(
    q_app, monkeypatch, tmp_path
):
    first_project = tmp_path / "first"
    first_project.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _stub_existing_directory(monkeypatch, first_project)
    _stub_text_input(monkeypatch, "First Project")
    tab._new_project()
    _bind_bible(tab, monkeypatch, tmp_path / "bibles")
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)
    tab._assign_correspondence()
    assert tab.correspondence_set() is not None

    second_project = tmp_path / "second"
    second_project.mkdir()
    _stub_existing_directory(monkeypatch, second_project)
    _stub_text_input(monkeypatch, "Second Project")
    tab._new_project()

    assert tab.correspondence_set() is None


def test_new_canvas_resets_correspondence_set_and_region_layers(q_app, monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    tab = ReferenceColoringTab()
    _new_canvas(tab, monkeypatch)
    _add_touching_region_layers(tab)
    _stub_existing_directory(monkeypatch, project_dir)
    _stub_text_input(monkeypatch, "Editor Project")
    tab._new_project()
    _bind_bible(tab, monkeypatch, tmp_path / "bibles")
    tab._layer_panel.select_layer("layer-1-region-1")
    tab._material_combo.setCurrentIndex(0)
    tab._assign_correspondence()
    assert tab.correspondence_set() is not None
    assert tab._region_layer_ids == ["layer-1-region-1", "layer-1-region-2"]

    _new_canvas(tab, monkeypatch)

    assert tab.correspondence_set() is None
    assert tab._region_layer_ids == []
