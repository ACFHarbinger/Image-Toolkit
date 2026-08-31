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
from .gcd_adapter import GCDCloudRunAdapter
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

__all__ = [
    "CloudJob",
    "CloudProviderAdapter",
    "CloudRunResult",
    "GCDCloudRunAdapter",
    "CloudflareAdapter",
    "OracleAdapter",
    "UsageRow",
    "UsageRowSource",
    "UsageSummary",
    "aggregate_usage_rows",
    "get_adapter",
]
