"""Cloud Compute Offload (roadmap §4.21) — client-side job model + provider
adapters.

`CloudJob` is the canonical, Qt-free description of one heavy request. Its
`to_job_json()` emits exactly the wire schema the provider worker containers
consume (see ``infra/cloud/gcd/worker/extraction.py``). A
`CloudProviderAdapter` submits a `CloudJob` to one provider and returns a
`CloudRunResult` (terminal status + output URIs + a usage row for the
Dashboards tab).

First PoC: `GCDCloudRunAdapter` → Google Cloud Run (`infra/cloud/gcd`).
Cloudflare / Oracle adapters are declared but not implemented yet.
"""

from __future__ import annotations

from .cloud_job import CloudJob
from .dispatcher import CloudExtractionDispatcher, DispatchResult
from .gcd_adapter import GCDCloudRunAdapter
from .gcs_client import GCSClient, parse_gs_uri
from .provider_adapter import (
    CloudflareAdapter,
    CloudProviderAdapter,
    CloudRunResult,
    OracleAdapter,
    get_adapter,
)
from .usage import (
    UsageRow,
    UsageRowSource,
    UsageSummary,
    aggregate_usage_rows,
)
from .usage_store import DEFAULT_USAGE_PATH, UsageStore

__all__ = [
    "CloudJob",
    "CloudProviderAdapter",
    "CloudRunResult",
    "CloudExtractionDispatcher",
    "DispatchResult",
    "GCDCloudRunAdapter",
    "GCSClient",
    "parse_gs_uri",
    "CloudflareAdapter",
    "OracleAdapter",
    "UsageRow",
    "UsageRowSource",
    "UsageSummary",
    "UsageStore",
    "DEFAULT_USAGE_PATH",
    "aggregate_usage_rows",
    "get_adapter",
]
