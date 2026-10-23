"""Default shortcut registry path is the repo-root contract."""

import json
from pathlib import Path

from middleware.src.shortcuts import registry
from middleware.src.shortcuts.registry import active_keys, keybindings_path, load_overrides, load_registry


def test_load_registry_reads_the_repo_root_contract():
    loaded = load_registry()
    assert loaded["version"] == 1
    assert any(action["id"] == "general.toggle_inspector" for action in loaded["actions"])
    zoom = next(action for action in loaded["actions"] if action["id"] == "preview.zoom_in")
    assert zoom["also"] == ["Ctrl+Shift++"]


def test_default_registry_path_prefers_the_frozen_bundle(monkeypatch, tmp_path: Path):
    bundled = tmp_path / "contracts" / "shortcuts" / "registry.json"
    bundled.parent.mkdir(parents=True)
    bundled.write_text(Path(registry.default_registry_path()).read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(registry.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert registry.default_registry_path() == bundled


def test_active_keys_drop_aliases_with_the_default():
    loaded = load_registry()
    assert active_keys(loaded, {}, "preview.zoom_in") == ["Ctrl+=", "Ctrl+Shift++"]
    disabled = {"preview.zoom_in": {"default_enabled": False, "custom": ["Ctrl+0"]}}
    assert active_keys(loaded, disabled, "preview.zoom_in") == ["Ctrl+0"]


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
