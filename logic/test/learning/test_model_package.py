"""Tests for offline, non-executing model package validation."""

import hashlib
import json

import pytest

from learning import (
    LocalModel,
    ModelPackageLimits,
    validate_model_package,
)


def _package(tmp_path, artifact=b"model bytes", **overrides):
    artifact_path = tmp_path / "weights.bin"
    artifact_path.write_bytes(artifact)
    manifest = {
        "schema_version": 1,
        "id": "landmarks",
        "version": "1",
        "format": "custom",
        "entrypoint": "weights.bin",
        "artifacts": [
            {
                "path": "weights.bin",
                "size": len(artifact),
                "sha256": hashlib.sha256(artifact).hexdigest(),
            }
        ],
    }
    manifest.update(overrides)
    (tmp_path / "model.json").write_text(json.dumps(manifest), encoding="utf-8")
    return LocalModel("landmarks", "1", str(tmp_path))


def test_validates_arbitrary_format_without_loading_it(tmp_path):
    model = _package(tmp_path, format="artist-custom-runtime")
    result = validate_model_package(model)
    assert result.total_bytes == len(b"model bytes")
    assert result.manifest.format == "artist-custom-runtime"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"id": "other"}, "identity"),
        ({"entrypoint": "../weights.bin"}, "safely relative"),
        ({"entrypoint": "missing.bin"}, "declared artifact"),
        ({"schema_version": 2}, "unsupported model package schema"),
    ],
)
def test_rejects_invalid_manifest_metadata(tmp_path, overrides, message):
    model = _package(tmp_path, **overrides)
    with pytest.raises(ValueError, match=message):
        validate_model_package(model)


def test_rejects_modified_artifact(tmp_path):
    model = _package(tmp_path)
    (tmp_path / "weights.bin").write_bytes(b"tampered!!!")
    with pytest.raises(ValueError, match="checksum mismatch"):
        validate_model_package(model)


def test_rejects_symlinked_artifact(tmp_path):
    model = _package(tmp_path)
    target = tmp_path / "outside.bin"
    target.write_bytes(b"model bytes")
    (tmp_path / "weights.bin").unlink()
    (tmp_path / "weights.bin").symlink_to(target)
    with pytest.raises(ValueError, match="not a regular file"):
        validate_model_package(model)


def test_enforces_configurable_resource_limits(tmp_path):
    model = _package(tmp_path)
    limits = ModelPackageLimits(max_artifacts=1, max_artifact_bytes=4, max_total_bytes=4)
    with pytest.raises(ValueError, match="size limit"):
        validate_model_package(model, limits)
