# Local model packages

Optional models are installed as local directories. Registration records where
a package is and who supplied it; validation checks integrity without importing
Python, loading tensors, or executing package content. The deterministic first
lesson does not require a model.

Each directory contains a `model.json` manifest and one or more artifacts:

```json
{
  "schema_version": 1,
  "id": "anime-landmarks",
  "version": "1.0.0",
  "format": "onnx",
  "entrypoint": "landmarks.onnx",
  "artifacts": [
    {
      "path": "landmarks.onnx",
      "size": 123456,
      "sha256": "<64 lowercase hexadecimal characters>"
    }
  ]
}
```

The manifest identity must match the registry record. Artifact paths must be
unique, package-relative POSIX paths; absolute paths, traversal, backslashes,
and symbolic links are rejected. Declared byte sizes and SHA-256 hashes must
match. Defaults permit at most 128 artifacts, 16 GiB per artifact, and 32 GiB
per package; callers can choose stricter limits.

`format` is intentionally extensible so artists may install packages for new or
custom runtimes. Integrity validation does **not** mean a model is safe or
compatible. `built_in`, `community`, and `unverified` provenance remains visible
and separate. A future runtime loader must enforce its own format-specific
sandbox and consent policy before deserializing anything.
