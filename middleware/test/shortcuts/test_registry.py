"""Default shortcut registry path is the repo-root contract."""

from middleware.src.shortcuts.registry import load_registry


def test_load_registry_reads_the_repo_root_contract():
    registry = load_registry()
    assert registry["version"] == 1
    assert any(action["id"] == "general.toggle_inspector" for action in registry["actions"])
