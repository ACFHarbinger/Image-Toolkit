"""Tests for coexistence packaging and version alignment (#886, W0-22)."""

from __future__ import annotations

from middleware.src.bridge.handshake import (
    accept_handshake_result,
    build_handshake_request,
    build_handshake_result,
    in_compatibility_range,
)
from middleware.src.supervisor.children import resolve_backend_python, sidecar_argv
from tools.release import bump, package_tauri


def test_in_compatibility_range():
    assert in_compatibility_range("1.0.0", minimum="1.0.0", maximum="1.0.0")
    assert in_compatibility_range("1.0.1", minimum="1.0.0", maximum="1.1.0")
    assert not in_compatibility_range("0.9.0", minimum="1.0.0", maximum="1.0.0")
    assert not in_compatibility_range("2.0.0", minimum="1.0.0", maximum="1.0.0")


def test_handshake_version_pair_accepts_matching():
    request = build_handshake_request("tauri-shell", "1.0.0")
    assert request["method"] == "system.handshake"
    assert request["params"]["client"]["version"] == "1.0.0"

    result = build_handshake_result(version="1.0.0")
    accepted = accept_handshake_result(
        {"jsonrpc": "2.0", "id": "hs", "result": result},
        client_version="1.0.0",
    )
    assert accepted["protocol"] == "image-toolkit-bridge"
    assert accepted["compatibility"] == {"min": "1.0.0", "max": "1.0.0"}


def test_resolve_backend_python_explicit(tmp_path):
    explicit = str(tmp_path / "custom_python")
    assert resolve_backend_python(explicit=explicit) == explicit


def test_resolve_backend_python_env_var(tmp_path, monkeypatch):
    custom_bin = tmp_path / "env_python"
    custom_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    custom_bin.chmod(0o755)

    monkeypatch.setenv("IMAGE_TOOLKIT_BACKEND_PYTHON", str(custom_bin))
    assert resolve_backend_python() == str(custom_bin)


def test_resolve_backend_python_runtime_env(tmp_path, monkeypatch):
    runtime_dir = tmp_path / "staged-runtime"
    py_bin = runtime_dir / "python" / "bin" / "python3"
    py_bin.parent.mkdir(parents=True)
    py_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    py_bin.chmod(0o755)

    monkeypatch.delenv("IMAGE_TOOLKIT_BACKEND_PYTHON", raising=False)
    monkeypatch.setenv("IMAGE_TOOLKIT_RUNTIME", str(runtime_dir))
    assert resolve_backend_python() == str(py_bin)


def test_resolve_backend_python_data_dir_pointer(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGE_TOOLKIT_BACKEND_PYTHON", raising=False)
    monkeypatch.delenv("IMAGE_TOOLKIT_RUNTIME", raising=False)

    py_bin = tmp_path / "pointer_python"
    py_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    py_bin.chmod(0o755)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "backend_python.txt").write_text(str(py_bin) + "\n", encoding="utf-8")

    assert resolve_backend_python(data_dir=data_dir) == str(py_bin)


def test_sidecar_argv_uses_resolved_python(tmp_path):
    fake_py = str(tmp_path / "python3")
    argv = sidecar_argv(tmp_path, python_executable=fake_py)
    assert argv == [fake_py, "-m", "middleware.src.sidecar", "--data-dir", str(tmp_path)]


def test_bump_rewrite_targets_synthetic(tmp_path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text('{\n  "name": "foo",\n  "version": "0.1.0"\n}\n')
    assert '"version": "1.2.3"' in bump._rewrite_package_json(pkg_json.read_text(), "1.2.3")

    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text('[package]\nname = "app"\nversion = "0.1.0"\n')
    assert 'version = "1.2.3"' in bump._rewrite_toml_version(cargo_toml.read_text(), "1.2.3", "package")


def test_package_tauri_dry_run(tmp_path):
    artifacts = package_tauri.build_tauri(tmp_path, "1.0.0", dry_run=True)
    assert len(artifacts) == 1
    assert artifacts[0].name == "image-toolkit-tauri_1.0.0_amd64.deb"
