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
    assert module.selected_material_id(Node("Material — hair")) == "hair"
    with pytest.raises(ValueError, match="named material mask"):
        module.selected_material_id(Node("Hair mask"))


def test_palette_preview_uses_mask_alpha_and_krita_bgra_order():
    pixels = _module().palette_preview_bgra(bytes((0, 128, 255)), "#A1B2C3")
    assert pixels == bytes((0xC3, 0xB2, 0xA1, 0, 0xC3, 0xB2, 0xA1, 128, 0xC3, 0xB2, 0xA1, 255))
