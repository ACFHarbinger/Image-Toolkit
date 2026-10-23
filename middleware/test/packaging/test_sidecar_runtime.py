"""Relocation smoke test using an empty venv backed by standalone Python."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def test_staged_runtime_launches_after_sources_are_removed(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "stage_runtime", repo / "frontend/src-tauri/scripts/stage_sidecar_runtime.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "source"
    source.mkdir()
    for name in ("middleware", "contracts"):
        shutil.copytree(repo / name, source / name, ignore=shutil.ignore_patterns("__pycache__", "test"))
    venv = source / ".venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    staged = tmp_path / "staged"
    module.stage(source, venv, staged)
    relocated = tmp_path / "installed"
    staged.rename(relocated)
    shutil.rmtree(source)
    assert not any(path.is_symlink() for path in relocated.rglob("*"))
    request = {
        "jsonrpc": "2.0",
        "id": "hs",
        "method": "system.handshake",
        "params": {"protocol": "image-toolkit-bridge", "client": {"name": "relocation-test", "version": "1.0.0"}},
    }
    result = subprocess.run(
        [
            str(relocated / "python/bin/python3"),
            "-I",
            "-c",
            "import sys,runpy; sys.path.insert(0,sys.argv.pop(1)); "
            "runpy.run_module('middleware.src.sidecar',run_name='__main__')",
            str(relocated),
        ],
        input=json.dumps(request) + "\n",
        text=True,
        capture_output=True,
        check=True,
        cwd=tmp_path,
        env={"PATH": os.defpath, "PYTHONNOUSERSITE": "1"},
        timeout=20,
    )
    response = json.loads(result.stdout.splitlines()[0])
    assert response["id"] == "hs"
    assert "result" in response, response
