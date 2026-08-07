import importlib.util
from pathlib import Path


def _module():
    path = (
        Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/value_masks.py"
    )
    spec = importlib.util.spec_from_file_location("value_masks", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Node:
    def __init__(self, name, data=b"", children=()):
        self._name, self._data, self._children = name, data, children

    def name(self):
        return self._name

    def childNodes(self):
        return self._children

    def pixelData(self, x, y, width, height):
        return self._data


def test_finds_nested_named_mask_and_samples_only_alpha():
    module = _module()
    pixels = bytes([10, 20, 30, 255] * 4)
    mask = Node("02 Front Form-Shadow Mask", pixels)
    root = Node("root", children=[Node("group", children=[mask])])
    assert module.find_named_node(root, mask.name()) is mask
    assert module.sampled_alpha_mask(mask, 0, 6, 4, side=2) == [1, 1, 1, 1]
