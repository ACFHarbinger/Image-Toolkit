"""Tests for the contract spine (W0-10, #874).

Targeted checks only — no suites. Core tests are stdlib-only; the deep
envelope-validation tests need ``jsonschema`` (present in the locked env,
guarded with importorskip so a dependency cleanup cannot break CI).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATE = ROOT / "generate.py"

spec = importlib.util.spec_from_file_location("contracts_generate", GENERATE)
generate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = generate
spec.loader.exec_module(generate)

jsonschema = pytest.importorskip("jsonschema", reason="locked-env optional deep validation")
referencing = pytest.importorskip("referencing", reason="jsonschema companion library")
Registry = referencing.Registry
Resource = referencing.Resource

validators = {}


def _registry() -> Registry:
    resources = [
        (schema["$id"], Resource.from_contents(schema))
        for schema in (
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((ROOT / "schemas").rglob("*.json"))
        )
    ]
    return Registry().with_resources(resources)


def _validator(rel_path: str) -> jsonschema.Draft202012Validator:
    if rel_path not in validators:
        schema = json.loads((ROOT / "schemas" / rel_path).read_text(encoding="utf-8"))
        validators[rel_path] = jsonschema.Draft202012Validator(schema, registry=_registry())
    return validators[rel_path]


def _load_generated_python():
    path = ROOT / "generated" / "python" / "contracts_generated.py"
    spec = importlib.util.spec_from_file_location("contracts_generated", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestSources:
    def test_schema_files_wellformed(self):
        schemas, _methods = generate.load_inputs()
        stems = [s.stem for s in schemas]
        assert len(stems) == len(set(stems)), "schema file stems must be unique"

    def test_methods_table_references_resolve(self):
        schemas, methods = generate.load_inputs()
        generate.collect_emittable(schemas, methods)  # exits hard on a bad ref
        channels = {row["name"] for row in methods["channel"]}
        for row in methods["method"]:
            for emitted in row["emits"]:
                assert emitted in channels, f"{row['name']} emits undefined channel {emitted}"
            capability = row["name"].split(".")[0]
            assert row["capability"] == capability, f"{row['name']}: capability column mismatch"

    def test_envelope_sections_present(self):
        _schemas, methods = generate.load_inputs()
        for key in ("request", "response", "error", "event"):
            assert key in methods["envelope"], f"methods.toml missing envelope.{key}"


class TestEnvelopeValidation:
    def test_request_accepts_valid_and_rejects_garbage(self):
        v = _validator("envelope/request.json")
        assert v.is_valid({"jsonrpc": "2.0", "id": 1, "method": "jobs.cancel", "params": {"job_id": "j1"}})
        assert not v.is_valid({"jsonrpc": "1.0", "id": 1, "method": "jobs.cancel"})
        assert not v.is_valid({"jsonrpc": "2.0", "id": 1})  # no method
        assert not v.is_valid({"jsonrpc": "2.0", "id": 1, "method": "NoDots"})
        assert not v.is_valid({"jsonrpc": "2.0", "id": 1, "method": "jobs.cancel", "extra": True})

    def test_response_enforces_result_xor_error(self):
        v = _validator("envelope/response.json")
        assert v.is_valid({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})
        assert v.is_valid(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32000,
                    "message": "capped",
                    "data": {"code": "jobs.capped", "retryable": False, "message_key": "jobs.capped"},
                },
            }
        )
        assert not v.is_valid({"jsonrpc": "2.0", "id": 1, "result": {}, "error": {}})  # both
        assert not v.is_valid({"jsonrpc": "2.0", "id": 1})  # neither
        assert not v.is_valid(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32000, "message": "x"},  # missing data envelope
            }
        )

    def test_error_envelope_requires_full_triplet(self):
        v = _validator("envelope/error.json")
        assert v.is_valid({"code": "jobs.not_found", "retryable": False, "message_key": "jobs.not_found"})
        assert not v.is_valid({"code": "jobs.not_found", "message_key": "jobs.not_found"})  # no retryable
        assert not v.is_valid({"code": "UPPER.CASE", "retryable": False, "message_key": "x"})
        assert not v.is_valid({"code": "nodots", "retryable": False, "message_key": "x"})

    def test_event_envelope(self):
        v = _validator("envelope/event.json")
        base = {
            "channel": "jobs",
            "seq": 1,
            "kind": "fact",
            "durable": True,
            "ts": "2026-10-20T12:00:00Z",
            "payload": {"job_id": "j1", "state": "running"},
        }
        assert v.is_valid(base)
        assert not v.is_valid({**base, "seq": 0})
        assert not v.is_valid({**base, "kind": "notification"})
        assert not v.is_valid({**base, "payload": "not-an-object"})


class TestGeneratedArtifacts:
    def test_check_mode_passes(self):
        result = subprocess.run(
            [sys.executable, str(GENERATE), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_python_module_imports_and_constructs(self):
        module = _load_generated_python()
        info = module.ClientInfo(name="webview", version="0.1.0")
        result = module.HandshakeResult(
            protocol="it.bridge",
            version="0.1.0",
            compatibility=module.Compatibility(min="0.1", max="0.2"),
            capabilities=["jobs"],
        )
        assert result.compatibility.min == "0.1"
        assert module.JobState.CANCELLED.value == "cancelled"
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            info.name = "other"

    @pytest.mark.skipif(shutil.which("rustfmt") is None, reason="rustfmt not on PATH")
    def test_rust_file_is_rustfmt_clean(self):
        result = subprocess.run(
            ["rustfmt", "--edition", "2021", "--check", str(ROOT / "generated" / "rust" / "contracts.rs")],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
