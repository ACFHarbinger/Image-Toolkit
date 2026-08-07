"""Tests for the Krita-to-engine process boundary."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_client():
    path = (
        Path(__file__).parents[2]
        / "integrations/krita/pykrita/cel_shaded_generator/engine_client.py"
    )
    spec = importlib.util.spec_from_file_location("krita_engine_client", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _landmarks():
    return {
        "cranium_center": [0.5, 0.4],
        "cranium_radius": 0.25,
        "centerline_top": [0.5, 0.15],
        "centerline_bottom": [0.5, 0.85],
        "eye_line_left": [0.3, 0.4],
        "eye_line_right": [0.7, 0.4],
        "jaw_left": [0.34, 0.65],
        "jaw_right": [0.66, 0.65],
        "chin": [0.5, 0.85],
    }


def test_client_calls_real_engine_module_without_shell():
    module = _load_client()
    client = module.EngineClient(
        [sys.executable, "-m", "cel_shaded_generator.learning.engine_protocol"]
    )
    result = client.review_front_head("attempt-1", _landmarks())
    assert result["id"] == "attempt-1"
    assert result["evidence"] == []


def test_client_rejects_mismatched_response(monkeypatch):
    module = _load_client()
    response = {
        "protocol_version": 1,
        "request_id": "another-request",
        "ok": True,
        "result": {},
    }
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(response).encode(), returncode=0),
    )
    with pytest.raises(RuntimeError, match="does not match"):
        module.EngineClient(["engine"]).review_front_head("attempt-1", _landmarks())


def test_client_converts_timeout_to_actionable_failure(monkeypatch):
    module = _load_client()

    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("engine", 5)

    monkeypatch.setattr(module.subprocess, "run", time_out)
    with pytest.raises(RuntimeError, match="timed out"):
        module.EngineClient(["engine"]).review_front_head("attempt-1", _landmarks())


def test_client_requires_explicitly_discoverable_engine(monkeypatch, tmp_path):
    module = _load_client()
    monkeypatch.delenv("CEL_SHADED_GENERATOR_ENGINE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="was not found"):
        module.EngineClient()


def test_client_discovers_valid_xdg_engine_configuration(monkeypatch, tmp_path):
    module = _load_client()
    engine = tmp_path / "engine"
    engine.write_text("#!/bin/sh\n", encoding="utf-8")
    engine.chmod(0o700)
    config = tmp_path / "cel-shaded-generator/krita.json"
    config.parent.mkdir()
    config.write_text(
        json.dumps({"schema_version": 1, "engine_executable": str(engine)}), encoding="utf-8"
    )
    monkeypatch.delenv("CEL_SHADED_GENERATOR_ENGINE", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert module.EngineClient().command == (str(engine),)
