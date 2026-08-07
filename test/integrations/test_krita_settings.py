"""Tests for atomic, opt-in Krita tutor settings."""

import importlib.util
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/settings.py"
    spec = importlib.util.spec_from_file_location("krita_settings", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shortcuts_default_unassigned_and_preserve_engine(tmp_path):
    module = _module()
    config = tmp_path / "krita.json"
    module.merge_engine_executable("/engine", config)
    module.save_shortcuts({"review": "Ctrl+R", "accept": "", "reject": "Esc"}, config)
    payload = module.load_config(config)
    assert payload["engine_executable"] == "/engine"
    assert payload["shortcuts"] == {"review": "Ctrl+R", "accept": "", "reject": "Esc"}
    assert not config.with_suffix(".json.tmp").exists()


def test_duplicate_shortcuts_are_rejected_without_replacing_config(tmp_path):
    module = _module()
    config = tmp_path / "krita.json"
    module.save_shortcuts({"review": "", "accept": "", "reject": ""}, config)
    original = config.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="unique"):
        module.save_shortcuts({"review": "Tab", "accept": "tab", "reject": ""}, config)
    assert config.read_text(encoding="utf-8") == original
