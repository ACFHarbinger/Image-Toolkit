"""Tests for D5 bundle/replay (#391).

Covers build_bundle (D20 redaction: captures only with the flag, zip and
folder modes), replay_bundle (re-runs the captured command under
telemetry, writes a new investigation), and the CLI wiring (bundle verb +
repro --from-bundle).
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest
from tool.host.bundle import build_bundle, replay_bundle
from tool.host.store import WorkspaceStore
from tool.model.session import TELEMETRY_DIR  # noqa: F401  (ensure model import)


@pytest.fixture
def store(tmp_path):
    root = tmp_path / "ws"
    root.mkdir()
    return WorkspaceStore(root=root)


@pytest.fixture
def investigation(store, tmp_path):
    """An investigation with notes, one linked session, and a run sidecar
    carrying the captured command (the D1 run record contract)."""
    inv = store.create_investigation("demo")
    inv.append_note("first observation", author="test")
    inv.append_note("second observation", author="test")

    tel = tmp_path / "telemetry"
    tel.mkdir()
    session_path = tel / "telemetry-4242.jsonl"
    session_path.write_text(json.dumps({"t": 0.0, "category": "a", "event": "e"}) + "\n", encoding="utf-8")
    inv.link_session(str(session_path))

    # D1 run sidecar: <session>.run.json with command/cwd/exit.
    sidecar = session_path.with_suffix(session_path.suffix + ".run.json")
    sidecar.write_text(
        json.dumps({
            "run": {
                "verb": "test",
                "command": [sys.executable, "-c", "print('replayed-ok')"],
                "cwd": str(tmp_path),
                "exit_code": 0,
            }
        }),
        encoding="utf-8",
    )
    return inv


class TestBuildBundle:
    def test_zip_excludes_captures_by_default(self, store, investigation, tmp_path):
        result = build_bundle(store, "demo", dest_dir=tmp_path, zip_out=True)
        assert result.path == tmp_path / "demo.zip"
        assert result.path.exists()
        with zipfile.ZipFile(result.path) as zf:
            names = set(zf.namelist())
        assert "demo/manifest.json" in names
        assert "demo/notes.jsonl" in names
        assert "demo/repro.sh" in names
        assert not any("captures/" in n for n in names), "D20: captures must stay local by default"
        # repro.sh should re-run the captured command
        with zipfile.ZipFile(result.path) as zf:
            script = zf.read("demo/repro.sh").decode()
        assert "exec " + sys.executable in script
        assert "replayed-ok" in script

    def test_include_captures_adds_telemetry_and_sidecar(self, store, investigation, tmp_path):
        result = build_bundle(store, "demo", dest_dir=tmp_path, zip_out=True, include_captures=True)
        assert result.n_captures == 2  # telemetry jsonl + run sidecar
        with zipfile.ZipFile(result.path) as zf:
            names = set(zf.namelist())
        assert "demo/captures/telemetry-4242.jsonl" in names
        assert "demo/captures/telemetry-4242.jsonl.run.json" in names

    def test_folder_mode_no_zip(self, store, investigation, tmp_path):
        result = build_bundle(store, "demo", dest_dir=tmp_path, zip_out=False)
        assert result.path == tmp_path / "demo"
        assert (result.path / "manifest.json").exists()
        assert (result.path / "notes.jsonl").exists()
        assert (result.path / "repro.sh").exists()
        manifest = json.loads((result.path / "manifest.json").read_text())
        assert manifest["name"] == "demo"
        assert manifest["sessions"]  # linked session recorded

    def test_no_command_bundle_omits_repro_script(self, store, tmp_path):
        inv = store.create_investigation("norepro")
        inv.append_note("just notes", author="test")
        result = build_bundle(store, "norepro", dest_dir=tmp_path, zip_out=False)
        assert not (result.path / "repro.sh").exists()

    def test_captures_include_in_root_run_sidecar(self, store, tmp_path):
        # cmd_repro writes repro.run.json inside the investigation when no
        # telemetry session was produced; --include-captures must carry it.
        inv = store.create_investigation("rootside")
        inv.append_note("note", author="test")
        sidecar = inv.root / "repro.run.json"
        sidecar.write_text(
            json.dumps({"run": {"command": ["echo", "hi"], "cwd": str(tmp_path)}}),
            encoding="utf-8",
        )
        result = build_bundle(store, "rootside", dest_dir=tmp_path, zip_out=True, include_captures=True)
        assert result.n_captures == 1
        with zipfile.ZipFile(result.path) as zf:
            names = set(zf.namelist())
        assert "rootside/captures/repro.run.json" in names
        # repro.sh is derived from that sidecar
        with zipfile.ZipFile(result.path) as zf:
            script = zf.read("rootside/repro.sh").decode()
        assert "exec echo hi" in script


class TestReplayBundle:
    def test_replays_command_and_writes_investigation(self, store, investigation, tmp_path):
        bundle = build_bundle(store, "demo", dest_dir=tmp_path, zip_out=True)
        result = replay_bundle(bundle.path, store)
        assert result["exit_code"] == 0
        assert result["investigation"].startswith("replay-demo-")
        assert "replayed-ok" in " ".join(result["command"])
        root = Path(result["root"])
        assert (root / "notes.jsonl").exists()
        notes = (root / "notes.jsonl").read_text()
        assert "replayed from bundle" in notes
        assert "exit=0" in notes

    def test_replays_from_folder_artifact(self, store, investigation, tmp_path):
        bundle = build_bundle(store, "demo", dest_dir=tmp_path, zip_out=False)
        result = replay_bundle(bundle.path, store)
        assert result["exit_code"] == 0
        assert result["investigation"].startswith("replay-demo-")

    def test_rejects_non_bundle_artifact(self, store, tmp_path):
        junk = tmp_path / "junk.zip"
        with zipfile.ZipFile(junk, "w") as zf:
            zf.writestr("readme.txt", "not a bundle")
        with pytest.raises(ValueError):
            replay_bundle(junk, store)


class TestCliWiring:
    def test_parser_exposes_bundle_verb(self):
        from tool.cli.parser import build_parser

        parser = build_parser()
        args = parser.parse_args(["bundle", "demo", "--include-captures", "--out", "/tmp/x"])
        assert args.command == "bundle"
        assert args.investigation == "demo"
        assert args.include_captures is True
        assert args.out == "/tmp/x"

    def test_repro_accepts_from_bundle(self):
        from tool.cli.parser import build_parser

        parser = build_parser()
        args = parser.parse_args(["repro", "--from-bundle", "demo.zip"])
        assert args.command == "repro"
        assert args.from_bundle == "demo.zip"

    def test_commands_table_registers_bundle(self):
        from tool.cli.parser import COMMANDS

        assert "bundle" in COMMANDS
        assert callable(COMMANDS["bundle"])
