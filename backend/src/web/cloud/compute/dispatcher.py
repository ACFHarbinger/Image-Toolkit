"""`CloudExtractionDispatcher` — run one extractor-tab extraction on a cloud
provider and bring the results home (#487, Cloud Compute Offload PoC).

Flow (all synchronous; the GUI runs this on a worker thread):

    local source ──upload──▶ gs://<source_bucket>/<prefix>/source<ext>
                              │
                    CloudJob.from_extraction_config
                              │
                     adapter.run(job)  ──▶  CloudRunResult (gs:// outputs + usage)
                              │
                    download each output ──▶ <output_dir>/<name>
                              │
                    UsageRow ──append──▶ UsageStore  (Dashboards tab reads this)

Qt-free and dependency-injected: pass fakes for ``adapter`` / ``gcs`` /
``usage_store`` to unit-test the whole path without GCP.
"""

from __future__ import annotations

import contextlib
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional

from .cloud_job import CloudJob
from .gcs_client import GCSClient, parse_gs_uri
from .provider_adapter import CloudProviderAdapter, CloudRunResult
from .usage import UsageRow
from .usage_store import UsageStore


@dataclass
class DispatchResult:
    ok: bool
    job_id: str
    provider: str
    local_paths: List[str] = field(default_factory=list)
    source_uri: str = ""
    run: Optional[CloudRunResult] = None
    usage_row: Optional[UsageRow] = None
    error: Optional[str] = None


class CloudExtractionDispatcher:
    def __init__(
        self,
        adapter: CloudProviderAdapter,
        *,
        source_bucket: str,
        output_dir: str,
        gcs: Optional[GCSClient] = None,
        usage_store: Optional[UsageStore] = None,
        object_prefix: str = "cloud-jobs",
    ) -> None:
        if not source_bucket:
            raise ValueError("CloudExtractionDispatcher needs a source_bucket")
        self._adapter = adapter
        self._bucket = source_bucket
        self._output_dir = output_dir
        self._gcs = gcs or GCSClient()
        self._usage = usage_store or UsageStore()
        self._prefix = object_prefix.strip("/")

    # ------------------------------------------------------------------ run
    def dispatch(
        self,
        extraction_config: Mapping[str, Any],
        *,
        job_id: Optional[str] = None,
        source_path: Optional[str] = None,
    ) -> DispatchResult:
        job_id = job_id or f"job-{uuid.uuid4().hex[:12]}"
        provider = getattr(self._adapter, "name", "cloud")
        src = source_path or extraction_config.get("video_path") or extraction_config.get("source_path")
        if not src:
            return DispatchResult(False, job_id, provider, error="no source video in the extraction config")

        try:
            source_uri = self._ensure_uploaded(str(src), job_id)
        except Exception as exc:  # upload failure is terminal, nothing ran
            return DispatchResult(False, job_id, provider, error=f"source upload failed: {exc}")

        job = CloudJob.from_extraction_config(
            extraction_config,
            source_uri=source_uri,
            job_id=job_id,
            output_prefix=f"{self._prefix}/{job_id}",
        )

        run = self._adapter.run(job)
        row = self._record_usage(run, job)

        if not run.ok:
            return DispatchResult(
                False, job_id, provider, source_uri=source_uri, run=run,
                usage_row=row, error=run.error or "cloud job failed",
            )

        local_paths: List[str] = []
        try:
            for uri in run.output_uris:
                _, name = parse_gs_uri(uri)
                dest = os.path.join(self._output_dir, os.path.basename(name))
                local_paths.append(self._gcs.download_file(uri, dest))
        except Exception as exc:
            return DispatchResult(
                False, job_id, provider, source_uri=source_uri, run=run,
                usage_row=row, local_paths=local_paths,
                error=f"result download failed: {exc}",
            )

        return DispatchResult(
            True, job_id, provider, local_paths=local_paths,
            source_uri=source_uri, run=run, usage_row=row,
        )

    # -------------------------------------------------------------- helpers
    def _ensure_uploaded(self, source: str, job_id: str) -> str:
        if source.startswith("gs://"):
            return source
        ext = os.path.splitext(source)[1] or ".mp4"
        object_name = f"{self._prefix}/{job_id}/source{ext}"
        return self._gcs.upload_file(source, self._bucket, object_name)

    def _record_usage(self, run: CloudRunResult, job: CloudJob) -> UsageRow:
        raw = dict(run.usage or {})
        raw.setdefault("job_id", job.job_id)
        raw.setdefault("provider", run.provider or getattr(self._adapter, "name", "cloud"))
        raw.setdefault("task", f"extract_{job.mode}")
        raw.setdefault("status", run.status)
        raw.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        row = UsageRow.from_mapping(raw)
        # a dashboards-only write failure must not fail the extraction
        with contextlib.suppress(OSError):
            self._usage.append(row)
        return row


__all__ = ["CloudExtractionDispatcher", "DispatchResult"]
