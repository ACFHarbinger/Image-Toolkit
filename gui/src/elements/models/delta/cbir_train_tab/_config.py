"""Tab-config collect/set_config/get_default_config (UnifiedTrainTab contract).

Extracted from ``cbir_train_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...protos.cbir_train_tab import CBIRTrainTabHostProtocol


class _ConfigMixin:
    """Collects/restores the full CBIRTrainTab UI state as a config dict."""

    def collect(self: "CBIRTrainTabHostProtocol") -> dict:
        """Return all widget values as a config dict."""
        return {
            "image_dir": self._img_dir.text().strip(),
            "output_dir": self._out_dir.text().strip() or "cbir_checkpoints",
            "val_split": self._val_split.value(),
            "backbone": self._backbone.currentData(),
            "embed_dim": self._embed_dim.currentData(),
            "proj_layers": self._proj_layers.value(),
            "freeze_backbone_epochs": self._freeze_epochs.value(),
            "image_size": self._image_size.currentData(),
            "loss_fn": self._loss_fn.currentData(),
            "temperature": self._temperature.value(),
            "triplet_margin": self._margin.value(),
            "jitter_strength": self._jitter.value(),
            "epochs": self._epochs.value(),
            "batch_size": self._batch_size.value(),
            "lr": self._lr.value(),
            "backbone_lr_scale": self._bb_lr_scale.value(),
            "warmup_epochs": self._warmup.value(),
            "num_workers": self._workers.value(),
            "amp": self._amp.isChecked(),
            # Index builder
            "ckpt_path": self._ckpt_path.text().strip(),
            "index_img_dir": self._index_img_dir.text().strip(),
            "index_out_dir": self._index_out_dir.text().strip(),
        }

    def set_config(self: "CBIRTrainTabHostProtocol", cfg: dict) -> None:
        """Restore widget values from a config dict."""
        _set = {
            "image_dir": lambda v: self._img_dir.setText(v),
            "output_dir": lambda v: self._out_dir.setText(v),
            "val_split": lambda v: self._val_split.setValue(float(v)),
            "backbone": lambda v: self._backbone.setCurrentIndex(
                max(0, self._backbone.findData(v))
            ),
            "embed_dim": lambda v: self._embed_dim.setCurrentIndex(
                max(0, self._embed_dim.findData(int(v)))
            ),
            "proj_layers": lambda v: self._proj_layers.setValue(int(v)),
            "freeze_backbone_epochs": lambda v: self._freeze_epochs.setValue(int(v)),
            "image_size": lambda v: self._image_size.setCurrentIndex(
                max(0, self._image_size.findData(int(v)))
            ),
            "loss_fn": lambda v: self._loss_fn.setCurrentIndex(
                max(0, self._loss_fn.findData(v))
            ),
            "temperature": lambda v: self._temperature.setValue(float(v)),
            "triplet_margin": lambda v: self._margin.setValue(float(v)),
            "jitter_strength": lambda v: self._jitter.setValue(float(v)),
            "epochs": lambda v: self._epochs.setValue(int(v)),
            "batch_size": lambda v: self._batch_size.setValue(int(v)),
            "lr": lambda v: self._lr.setValue(float(v)),
            "backbone_lr_scale": lambda v: self._bb_lr_scale.setValue(float(v)),
            "warmup_epochs": lambda v: self._warmup.setValue(int(v)),
            "num_workers": lambda v: self._workers.setValue(int(v)),
            "amp": lambda v: self._amp.setChecked(bool(v)),
            "ckpt_path": lambda v: self._ckpt_path.setText(v),
            "index_img_dir": lambda v: self._index_img_dir.setText(v),
            "index_out_dir": lambda v: self._index_out_dir.setText(v),
        }
        for key, setter in _set.items():
            if key in cfg:
                with contextlib.suppress(Exception):
                    setter(cfg[key])

    def get_default_config(self) -> dict:
        return {
            "image_dir": "",
            "output_dir": "cbir_checkpoints",
            "val_split": 0.10,
            "backbone": "clip",
            "embed_dim": 256,
            "proj_layers": 2,
            "freeze_backbone_epochs": 2,
            "image_size": 224,
            "loss_fn": "infonce",
            "temperature": 0.07,
            "triplet_margin": 0.30,
            "jitter_strength": 0.5,
            "epochs": 20,
            "batch_size": 64,
            "lr": 3e-4,
            "backbone_lr_scale": 0.1,
            "warmup_epochs": 2,
            "num_workers": 4,
            "amp": True,
            "ckpt_path": "",
            "index_img_dir": "",
            "index_out_dir": str(Path.home() / ".image-toolkit" / "cbir_index"),
        }


__all__ = ["_ConfigMixin"]
