"""`GCDCloudRunAdapter` — dispatch a :class:`CloudJob` to the Google Cloud
Run worker (``infra/cloud/gcd``).

The worker's ``POST /jobs`` runs the extraction synchronously and returns the
usage row, so ``run()`` is one blocking request. Cloud Run private services
need a Google-signed ID token; pass ``id_token_provider`` (a zero-arg
callable returning the token string) to have it added as a Bearer header.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import requests

from .cloud_job import CloudJob
from .provider_adapter import CloudProviderAdapter, CloudRunResult

# Cloud Run request timeout ceiling is 3600s; the worker caps each ffmpeg
# phase at 1700s. Give the HTTP call headroom over a two-phase (gif) job.
_DEFAULT_TIMEOUT = 3600


class GCDCloudRunAdapter(CloudProviderAdapter):
    name = "gcd"

    def __init__(
        self,
        service_url: str,
        *,
        id_token_provider: Optional[Callable[[], str]] = None,
        session: Optional[requests.Session] = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        if not service_url:
            raise ValueError("GCDCloudRunAdapter needs the Cloud Run service_url")
        self._url = service_url.rstrip("/")
        self._id_token_provider = id_token_provider
        self._s = session or requests.Session()
        self._timeout = timeout

    # ------------------------------------------------------------------ auth
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._id_token_provider is not None:
            token = self._id_token_provider()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return headers

    # ------------------------------------------------------------------- run
    def run(self, job: CloudJob) -> CloudRunResult:
        try:
            resp = self._s.post(
                f"{self._url}/jobs",
                json=job.to_job_json(),
                headers=self._headers(),
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            return CloudRunResult(
                job_id=job.job_id, provider=self.name, status="error",
                error=f"request failed: {exc}",
            )

        row: dict
        try:
            row = resp.json()
        except ValueError:
            row = {}

        if resp.status_code != 200:
            return CloudRunResult(
                job_id=job.job_id, provider=self.name, status="error",
                usage=row,
                error=row.get("error") or f"HTTP {resp.status_code}: {resp.text[:200]}",
            )
        return CloudRunResult.from_usage_row(self.name, job.job_id, row)

    # --------------------------------------------------------------- healthz
    def healthz(self) -> bool:
        try:
            r = self._s.get(
                f"{self._url}/healthz", headers=self._headers(), timeout=15
            )
            return r.status_code == 200
        except requests.RequestException:
            return False

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"GCDCloudRunAdapter(service_url={self._url!r})"


def _default_id_token_provider(audience: str) -> Callable[[], str]:  # pragma: no cover
    """ID-token provider backed by google-auth (used in production, not tests).

    Imported lazily so the module has no hard google-auth dependency.
    """

    def _provider() -> str:
        import google.auth.transport.requests
        import google.oauth2.id_token

        req = google.auth.transport.requests.Request()
        return google.oauth2.id_token.fetch_id_token(req, audience)

    return _provider


__all__ = ["GCDCloudRunAdapter"]
