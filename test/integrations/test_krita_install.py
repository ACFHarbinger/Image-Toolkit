"""Tests for the scoped Krita plugin installer."""

from pathlib import Path

import pytest

from integrations.krita.install import default_root, install, uninstall


def test_install_and_uninstall_are_scoped(tmp_path):
    unrelated = tmp_path / "other.desktop"
    unrelated.write_text("keep", encoding="utf-8")

    install(tmp_path)
    assert (tmp_path / "cel_shaded_generator.desktop").is_file()
    assert (tmp_path / "cel_shaded_generator" / "content" / "lesson.json").is_file()

    uninstall(tmp_path)
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "cel_shaded_generator.desktop").exists()
    assert not (tmp_path / "cel_shaded_generator").exists()


def test_installer_refuses_to_overwrite_existing_plugin(tmp_path):
    (tmp_path / "cel_shaded_generator").mkdir()

    try:
        install(tmp_path)
    except FileExistsError as error:
        assert "uninstall" in str(error)
    else:
        raise AssertionError("installer overwrote an existing plugin")


def test_installer_excludes_python_cache_artifacts(tmp_path):
    source_cache = (
        Path(__file__).parents[2] / "integrations/krita/pykrita/cel_shaded_generator/__pycache__"
    )
    source_cache.mkdir(exist_ok=True)
    (source_cache / "generated.pyc").write_bytes(b"cache")

    install(tmp_path)

    assert not (tmp_path / "cel_shaded_generator" / "__pycache__").exists()


def test_default_root_uses_standard_linux_resource_path(monkeypatch, tmp_path):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    assert default_root() == tmp_path / ".local/share/krita/pykrita"


def test_snap_target_is_rejected(tmp_path):
    snap_root = tmp_path / "snap/krita/current/.local/share/krita/pykrita"
    with pytest.raises(RuntimeError, match="omits Python plugin support"):
        install(snap_root)
