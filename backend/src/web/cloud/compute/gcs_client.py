"""Thin Google Cloud Storage helper for the Cloud Compute PoC (#487).

Uploads the extractor source to a ``gs://`` object the Cloud Run worker can
read, and pulls the worker's ``gs://`` outputs back to the local extraction
directory. ``google-cloud-storage`` is imported lazily so the module (and
its unit tests) load without the dependency or any credentials.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple


def parse_gs_uri(uri: str) -> Tuple[str, str]:
    """``gs://bucket/a/b.mp4`` -> ``("bucket", "a/b.mp4")``."""
    if not uri.startswith("gs://"):
        raise ValueError(f"not a gs:// URI: {uri!r}")
    bucket, _, name = uri[len("gs://"):].partition("/")
    if not bucket or not name:
        raise ValueError(f"gs:// URI needs a bucket and object name: {uri!r}")
    return bucket, name


class GCSClient:
    """Minimal object upload/download over ``google.cloud.storage``."""

    def __init__(self, *, project: Optional[str] = None, _client: object = None) -> None:
        self._project = project
        self._explicit_client = _client
        self.__client = None

    # ------------------------------------------------------------------ lazy
    @property
    def _client(self):
        if self._explicit_client is not None:
            return self._explicit_client
        if self.__client is None:
            from google.cloud import storage  # lazy: optional dep

            self.__client = storage.Client(project=self._project)
        return self.__client

    # --------------------------------------------------------------- upload
    def upload_file(self, local_path: str, bucket: str, object_name: str) -> str:
        """Upload *local_path* to ``gs://bucket/object_name``; return that URI."""
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)
        blob = self._client.bucket(bucket).blob(object_name)
        blob.upload_from_filename(local_path)
        return f"gs://{bucket}/{object_name}"

    # ------------------------------------------------------------- download
    def download_file(self, gs_uri: str, local_path: str) -> str:
        """Download ``gs://…`` to *local_path* (parents created); return it."""
        bucket, name = parse_gs_uri(gs_uri)
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        self._client.bucket(bucket).blob(name).download_to_filename(local_path)
        return local_path


__all__ = ["GCSClient", "parse_gs_uri"]
