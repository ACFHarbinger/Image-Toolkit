import importlib.util
from pathlib import Path

import pytest


def _module():
    path = (
        Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/color_masks.py"
    )
    spec = importlib.util.spec_from_file_location("color_masks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Node:
    def __init__(self, name):
        self._name = name

    def name(self):
        return self._name


def test_material_mask_contract_is_canonical():
    module = _module()
    assert module.material_mask_name("hair") == "Material — hair"
    assert module.material_mask_name("hair", "back") == "Material — hair — back"
    assert module.selected_material_id(Node("Material — hair")) == "hair"
    assert module.selected_material_id(Node("Material — hair — back")) == "hair"
    assert module.material_mask_parts(Node("Material — hair — back")) == ("hair", "back")
    with pytest.raises(ValueError, match="named material mask"):
        module.selected_material_id(Node("Hair mask"))


def test_palette_preview_uses_mask_alpha_and_krita_bgra_order():
    pixels = _module().palette_preview_bgra(bytes((0, 128, 255)), "#A1B2C3")
    assert pixels == bytes((0xC3, 0xB2, 0xA1, 0, 0xC3, 0xB2, 0xA1, 128, 0xC3, 0xB2, 0xA1, 255))


def test_overlapping_materials_reports_each_ambiguous_pixel_count():
    conflicts = _module().overlapping_materials(
        "hair",
        {
            "hair": bytes((0, 255, 255, 0)),
            "skin": bytes((0, 0, 128, 0)),
            "eyes": bytes((0, 255, 0, 0)),
        },
    )
    assert conflicts == {"skin": 1, "eyes": 1}


def test_overlapping_materials_rejects_incomparable_buffers():
    with pytest.raises(ValueError, match="equal-length"):
        _module().overlapping_materials("hair", {"hair": b"\x00", "skin": b""})


def test_union_alpha_buffers_combines_material_variants():
    assert _module().union_alpha_buffers((bytes((0, 20, 0)), bytes((10, 0, 30)))) == bytes(
        (10, 20, 30)
    )


def test_union_alpha_buffers_rejects_empty_or_incomparable_inputs():
    with pytest.raises(ValueError, match="at least one"):
        _module().union_alpha_buffers(())
    with pytest.raises(ValueError, match="equal-length"):
        _module().union_alpha_buffers((b"\x00", b"\x00\x01"))


def test_material_mask_variant_names_preserve_canonical_material_identity():
    module = _module()
    assert module.material_mask_name("skin", "face") == "Material — skin — face"
    assert module.material_mask_parts(Node("Material — skin — face")) == ("skin", "face")


def test_region_id_from_layer_name_normalizes_arbitrary_layer_names():
    module = _module()
    assert module.region_id_from_layer_name("Hair Front (Large)") == "hair-front-large"
    assert module.region_id_from_layer_name("  Skin_Face!!  ") == "skin-face"


def test_region_id_from_layer_name_rejects_empty_or_unusable_names():
    module = _module()
    with pytest.raises(ValueError, match="must not be empty"):
        module.region_id_from_layer_name("   ")
    with pytest.raises(ValueError, match="no usable identifier"):
        module.region_id_from_layer_name("###")
