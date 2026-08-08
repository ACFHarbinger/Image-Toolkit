"""Offline integrity validation for locally installed model packages.

Validation never imports or deserializes an artifact.  A valid package is intact
and internally consistent; its trust label separately describes provenance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .model import LocalModel

MODEL_PACKAGE_SCHEMA_VERSION = 1
MODEL_MANIFEST_NAME = "model.json"


@dataclass(frozen=True, slots=True)
class Artifact:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ModelPackageManifest:
    id: str
    version: str
    format: str
    entrypoint: str
    artifacts: tuple[Artifact, ...]
    schema_version: int = MODEL_PACKAGE_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelPackageManifest:
        try:
            artifacts = tuple(Artifact(**item) for item in payload["artifacts"])
            manifest = cls(
                id=payload["id"],
                version=payload["version"],
                format=payload["format"],
                entrypoint=payload["entrypoint"],
                artifacts=artifacts,
                schema_version=payload.get("schema_version", 0),
            )
        except (KeyError, TypeError) as error:
            raise ValueError("invalid model manifest structure") from error
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if self.schema_version != MODEL_PACKAGE_SCHEMA_VERSION:
            raise ValueError(f"unsupported model package schema: {self.schema_version}")
        if not self.id.strip() or not self.version.strip() or not self.format.strip():
            raise ValueError("model id, version, and format must not be empty")
        if not self.artifacts:
            raise ValueError("model package must declare at least one artifact")
        paths = [artifact.path for artifact in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("model artifact paths must be unique")
        for artifact in self.artifacts:
            _validate_relative_path(artifact.path)
            if artifact.size < 0:
                raise ValueError("model artifact size must not be negative")
            if len(artifact.sha256) != 64 or any(
                character not in "0123456789abcdef" for character in artifact.sha256
            ):
                raise ValueError("model artifact SHA-256 must be lowercase hexadecimal")
        _validate_relative_path(self.entrypoint)
        if self.entrypoint not in paths:
            raise ValueError("model entrypoint must name a declared artifact")


@dataclass(frozen=True, slots=True)
class ModelPackageLimits:
    max_artifacts: int = 128
    max_artifact_bytes: int = 16 * 1024**3
    max_total_bytes: int = 32 * 1024**3


@dataclass(frozen=True, slots=True)
class ValidatedModelPackage:
    root: Path
    manifest: ModelPackageManifest
    total_bytes: int


def validate_model_package(
    model: LocalModel, limits: ModelPackageLimits | None = None
) -> ValidatedModelPackage:
    """Validate package metadata and bytes without executing model content."""
    limits = limits or ModelPackageLimits()
    root = Path(model.path).expanduser()
    if not root.is_dir() or root.is_symlink():
        raise ValueError("model package path must be a real directory")
    manifest_path = root / MODEL_MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError(f"model package must contain a regular {MODEL_MANIFEST_NAME}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("model manifest is not valid UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("model manifest root must be an object")
    manifest = ModelPackageManifest.from_dict(payload)
    if (manifest.id, manifest.version) != (model.id, model.version):
        raise ValueError("model manifest identity does not match registry record")
    if len(manifest.artifacts) > limits.max_artifacts:
        raise ValueError("model package contains too many artifacts")

    total_bytes = 0
    for artifact in manifest.artifacts:
        candidate = root / artifact.path
        if not candidate.is_file() or candidate.is_symlink():
            raise ValueError(f"model artifact is missing or not a regular file: {artifact.path}")
        actual_size = candidate.stat().st_size
        if actual_size != artifact.size:
            raise ValueError(f"model artifact size mismatch: {artifact.path}")
        if actual_size > limits.max_artifact_bytes:
            raise ValueError(f"model artifact exceeds size limit: {artifact.path}")
        total_bytes += actual_size
        if total_bytes > limits.max_total_bytes:
            raise ValueError("model package exceeds total size limit")
        if _sha256(candidate) != artifact.sha256:
            raise ValueError(f"model artifact checksum mismatch: {artifact.path}")
    return ValidatedModelPackage(root.resolve(), manifest, total_bytes)


def _validate_relative_path(value: str) -> None:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"model artifact path is not safely relative: {value!r}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
