"""Cloud Run HTTP entrypoint for FFmpeg-only extractor jobs."""

from __future__ import annotations

import json
import os
import resource
import shutil
import tempfile
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from extraction import ExtractionJob, build_commands, run_commands


def _split_gs_uri(uri: str) -> tuple[str, str]:
    bucket, _, name = uri.removeprefix("gs://").partition("/")
    if not bucket or not name:
        raise ValueError("gs:// URI must include a bucket and object name")
    return bucket, name


def _storage_client():
    from google.cloud import storage

    return storage.Client()


def execute_job(payload: dict[str, Any]) -> dict[str, Any]:
    """Download, extract, upload outputs, and return a durable usage row."""
    job = ExtractionJob.from_json(payload)
    result_bucket = os.environ.get("RESULTS_BUCKET")
    if not result_bucket:
        raise RuntimeError("RESULTS_BUCKET must be configured")
    client = _storage_client()
    source_bucket, source_name = _split_gs_uri(job.source_uri)
    started = time.monotonic()
    workdir = Path(tempfile.mkdtemp(prefix=f"itk-{job.job_id}-"))
    try:
        source = workdir / "source"
        output_dir = workdir / "outputs"
        output_dir.mkdir()
        client.bucket(source_bucket).blob(source_name).download_to_filename(source)
        run_commands(build_commands(job, source, output_dir))
        output_uris = []
        bucket = client.bucket(result_bucket)
        for path in output_dir.iterdir():
            if path.name == "palette.png":
                continue
            object_name = f"{job.output_prefix.rstrip('/')}/{path.name}"
            bucket.blob(object_name).upload_from_filename(path)
            output_uris.append(f"gs://{result_bucket}/{object_name}")
        elapsed = round(time.monotonic() - started, 3)
        usage = {
            "job_id": job.job_id,
            "provider": "gcd",
            "task": f"extract_{job.mode}",
            "status": "success",
            "duration_seconds": elapsed,
            "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "output_uris": output_uris,
        }
        bucket.blob(f"{job.output_prefix.rstrip('/')}/usage.json").upload_from_string(
            json.dumps(usage), content_type="application/json"
        )
        return usage
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/jobs":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 64 * 1024:
                raise ValueError("job JSON must be between 1 and 65536 bytes")
            result = execute_job(json.loads(self.rfile.read(length)))
            self._json(HTTPStatus.OK, result)
        except Exception as error:
            self._json(HTTPStatus.BAD_REQUEST, {"status": "error", "error": str(error)})

    def log_message(self, _format: str, *_args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()
