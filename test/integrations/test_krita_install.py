"""Tests for the scoped Krita plugin installer."""

import json
from pathlib import Path

import pytest

from integrations.krita.install import configure_engine, default_root, install, uninstall


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


def test_packaged_lesson_is_a_complete_offline_beginner_sequence():
    path = (
        Path(__file__).parents[2]
        / "integrations/krita/pykrita/cel_shaded_generator/content/lesson.json"
    )
    lesson = json.loads(path.read_text(encoding="utf-8"))
    assert lesson["schema_version"] == 1
    assert lesson["method_id"] == "anime-head-construction-v1"
    assert len(lesson["steps"]) == 5
    assert len(lesson["completion_criteria"]) == 5
    assert "memory" in lesson["practice_prompt"].lower()


def test_engine_configuration_is_explicit_and_atomic(tmp_path):
    engine = tmp_path / "engine"
    engine.write_text("#!/bin/sh\n", encoding="utf-8")
    engine.chmod(0o700)
    config = tmp_path / "config/krita.json"
    assert configure_engine(engine, config) == config
    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload == {"schema_version": 1, "engine_executable": str(engine.resolve())}
    assert not config.with_suffix(".json.tmp").exists()


def test_engine_configuration_rejects_non_executable(tmp_path):
    engine = tmp_path / "engine"
    engine.write_text("not executable", encoding="utf-8")
    with pytest.raises(ValueError, match="executable"):
        configure_engine(engine, tmp_path / "krita.json")
