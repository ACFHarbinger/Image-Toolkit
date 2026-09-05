"""Unit tests for SafetensorsInspectorDialog (new_features.md §4.9)."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gui.src.components.dialogs.safetensors_inspector_dialog import (
    SafetensorsInspectorDialog,
)

if not QApplication.instance():
    app = QApplication(sys.argv)


def test_safetensors_inspector_dialog_populate():
    dlg = SafetensorsInspectorDialog("/tmp/fake_model.safetensors")
    fake_data = {
        "file_size_mb": 128.5,
        "tensor_count": 197,
        "param_count": 123456789,
        "dtype_counts": {"F16": 190, "F32": 7},
        "parsed_spec": {
            "rank": "32",
            "alpha": "16",
            "base_model": "Illustrious XL",
            "trigger_words": "1girl, masterpiece",
            "embedded_hash": "abcdef1234567890",
        },
        "user_meta": {
            "modelspec.title": "My Character LoRA",
            "ss_network_dim": "32",
        },
        "tensors": {
            "lora_unet_down_blocks_0_attentions_0_proj_in.lora_down.weight": {
                "shape": [32, 320],
                "dtype": "F16",
            },
            "lora_unet_down_blocks_0_attentions_0_proj_in.lora_up.weight": {
                "shape": [320, 32],
                "dtype": "F16",
            },
        },
    }

    dlg._populate(fake_data)

    # Verify Summary items
    summary_items = [
        (dlg._summary_tree.topLevelItem(i).text(0), dlg._summary_tree.topLevelItem(i).text(1))
        for i in range(dlg._summary_tree.topLevelItemCount())
    ]
    summary_dict = dict(summary_items)
    assert summary_dict["File"] == "fake_model.safetensors"
    assert summary_dict["Size"] == "128.5 MB"
    assert summary_dict["Base Model"] == "Illustrious XL"
    assert summary_dict["LoRA Rank"] == "32"
    assert summary_dict["LoRA Alpha"] == "16"
    assert summary_dict["Trigger Words"] == "1girl, masterpiece"
    assert summary_dict["Tensors"] == "197"
    assert "123.46 M" in summary_dict["Parameters"]

    # Verify User Metadata items
    meta_items = [
        (dlg._meta_tree.topLevelItem(i).text(0), dlg._meta_tree.topLevelItem(i).text(1))
        for i in range(dlg._meta_tree.topLevelItemCount())
    ]
    meta_dict = dict(meta_items)
    assert meta_dict["modelspec.title"] == "My Character LoRA"
    assert meta_dict["ss_network_dim"] == "32"

    # Verify Tensors tree
    assert dlg._tensor_tree.topLevelItemCount() == 2
    t0 = dlg._tensor_tree.topLevelItem(0)
    assert "lora_unet" in t0.text(0)
    assert t0.text(2) == "F16"


def test_safetensors_inspector_hash_verification():
    dlg = SafetensorsInspectorDialog("/tmp/fake_model.safetensors")
    dlg._raw_data = {
        "parsed_spec": {
            "embedded_hash": "abcdef1234567890",
        }
    }

    dlg._on_hash_computed("abcdef1234567890deadbeef")
    assert dlg._computed_hash == "abcdef1234567890deadbeef"
    assert dlg._hash_btn.text() == "SHA256 Verified"

    # Check that verification item was added with MATCHED status
    summary_items = [
        (dlg._summary_tree.topLevelItem(i).text(0), dlg._summary_tree.topLevelItem(i).text(1))
        for i in range(dlg._summary_tree.topLevelItemCount())
    ]
    summary_dict = dict(summary_items)
    assert "Integrity Verification" in summary_dict
    assert summary_dict["Integrity Verification"] == "✓ MATCHED"


def test_safetensors_inspector_copy_metadata():
    dlg = SafetensorsInspectorDialog("/tmp/fake_model.safetensors")
    dlg._raw_data = {
        "file_size_mb": 50.0,
        "tensor_count": 10,
        "param_count": 50000,
        "user_meta": {"tag": "anime"},
    }
    dlg._computed_hash = "1234567890abcdef"
    dlg._copy_metadata()

    clipboard_text = QApplication.clipboard().text()
    assert "File: /tmp/fake_model.safetensors" in clipboard_text
    assert "Size: 50.0 MB" in clipboard_text
    assert "SHA256: 1234567890abcdef" in clipboard_text
    assert "tag: anime" in clipboard_text
