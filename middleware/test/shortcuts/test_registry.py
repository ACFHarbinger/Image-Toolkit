"""Default shortcut registry path is the repo-root contract."""

import json
from pathlib import Path

from middleware.src.shortcuts import registry
from middleware.src.shortcuts.registry import keybindings_path, load_overrides, load_registry


def test_load_registry_reads_the_repo_root_contract():
    loaded = load_registry()
    assert loaded["version"] == 1
    assert any(action["id"] == "general.toggle_inspector" for action in loaded["actions"])


def test_load_overrides_does_not_import_the_gui(monkeypatch, tmp_path: Path):
    source = Path(registry.__file__).read_text(encoding="utf-8")
    assert "import gui" not in source
    assert "from gui" not in source
    assert "import PySide6" not in source
    assert "from PySide6" not in source
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert keybindings_path() == tmp_path / ".image-toolkit" / "keybindings.json"
    assert load_overrides() == {}

    path = tmp_path / "keybindings.json"
    path.write_text(
        json.dumps(
            {
                "gallery.select_all": "Meta+A",
                "general.toggle_inspector": {"default_enabled": False, "custom": ["Ctrl+I", ""]},
            }
        ),
        encoding="utf-8",
    )
    overrides = load_overrides(path)
    assert overrides["gallery.select_all"] == {"default_enabled": False, "custom": ["Meta+A"]}
    assert overrides["general.toggle_inspector"]["custom"] == ["Ctrl+I"]
