"""Delta (fine-tuning) train tabs. ``StitchTrainTab`` lives in the ASP
submodule and is resolved lazily (ui-arch-27/#549) so importing this package
never imports ``asp_gui``."""

import importlib

from .gan_train_tab import GANTrainTab as GANTrainTab
from .lora_train_tab import LoRATrainTab as LoRATrainTab
from .r3gan_train_tab import R3GANTrainTab as R3GANTrainTab

_LAZY_SUBMODULE_EXPORTS = {"StitchTrainTab": "asp_gui.tabs.models.delta.stitch_train_tab"}


def __getattr__(name):
    if name in _LAZY_SUBMODULE_EXPORTS:
        value = getattr(importlib.import_module(_LAZY_SUBMODULE_EXPORTS[name]), name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
