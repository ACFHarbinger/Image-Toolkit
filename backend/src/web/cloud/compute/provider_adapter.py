"""`CloudProviderAdapter` ABC + shared result type + not-yet-implemented
Cloudflare / Oracle stubs.

The GCD PoC worker is *synchronous* (``POST /jobs`` blocks until the
extraction finishes and returns the usage row), so the adapter contract is a
single ``run(job) -> CloudRunResult``. Async providers can later add polling
without changing callers that only need the terminal result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .cloud_job import CloudJob


@dataclass(frozen=True)
class CloudRunResult:
    """Terminal outcome of one cloud job."""

    job_id: str
    provider: str
    status: str  # "success" | "error"
    output_uris: List[str] = field(default_factory=list)
    usage: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status == "success"

    @classmethod
    def from_usage_row(cls, provider: str, job_id: str, row: Dict[str, Any]) -> "CloudRunResult":
        """Build from the worker's returned usage JSON (see
        ``infra/cloud/gcd/worker/server.py``)."""
        status = str(row.get("status", "success"))
        return cls(
            job_id=row.get("job_id", job_id),
            provider=provider,
            status=status,
            output_uris=list(row.get("output_uris", []) or []),
            usage=dict(row),
            error=row.get("error") if status != "success" else None,
        )


class CloudProviderAdapter(ABC):
    """Submit a :class:`CloudJob` to one provider and return its result."""

    name: str = "base"

    @abstractmethod
    def run(self, job: CloudJob) -> CloudRunResult:
        """Dispatch *job* and block until it reaches a terminal state."""

    def healthz(self) -> bool:
        """Best-effort provider reachability check. Adapters may override."""
        return True


class _UnimplementedAdapter(CloudProviderAdapter):
    _roadmap = "roadmap §4.21"

    def run(self, job: CloudJob) -> CloudRunResult:
        raise NotImplementedError(
            f"{self.name} cloud offload is not implemented yet ({self._roadmap}); "
            "only Google Cloud Run (GCD) is wired for the PoC."
        )

    def healthz(self) -> bool:
        return False


class CloudflareAdapter(_UnimplementedAdapter):
    name = "cloudflare"


class OracleAdapter(_UnimplementedAdapter):
    name = "oracle"


# provider id -> adapter factory. GCD needs a service URL so it is not
# registered here; use GCDCloudRunAdapter(...) directly (see get_adapter).
_STUB_ADAPTERS = {
    "cloudflare": CloudflareAdapter,
    "oracle": OracleAdapter,
}


def get_adapter(provider_id: str, **kwargs: Any) -> CloudProviderAdapter:
    """Return an adapter for ``provider_id`` (``"gcd"`` / ``"cloudflare"`` /
    ``"oracle"``). ``gcd`` requires ``service_url=...``."""
    pid = provider_id.strip().lower()
    if pid in ("gcd", "google", "google-cloud", "cloud-run"):
        from .gcd_adapter import GCDCloudRunAdapter

        return GCDCloudRunAdapter(**kwargs)
    if pid in _STUB_ADAPTERS:
        return _STUB_ADAPTERS[pid]()
    raise ValueError(f"unknown cloud provider {provider_id!r}")


__all__ = [
    "CloudProviderAdapter",
    "CloudRunResult",
    "CloudflareAdapter",
    "OracleAdapter",
    "get_adapter",
]
