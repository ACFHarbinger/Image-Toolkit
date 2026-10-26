"""Cloud Compute provider catalog (T-04 / #920).

Qt-free mirror of the Qt providers pane's ``DEFAULT_PROVIDERS``
(``gui/src/windows/cloud/providers_pane.py``): the descriptor fields ride
the bridge verbatim except ``badge_color``, which becomes a theme-token
name instead of a resolved RGB value — the webview maps tokens to CSS
variables. This module opens no vault and holds no credentials; provider
account setup writes only non-secret config through the settings service,
and attaching real credentials rides the vault unlock (#918 / #879).
"""

from __future__ import annotations

from typing import Any

_PROVIDER_CATALOG: list[dict[str, Any]] = [
    {
        "provider_id": "gcd",
        "name": "Google Cloud Run (GCD)",
        "badge_text": "Active PoC Target",
        "badge_token": "success",
        "description": (
            "Serverless container compute powered by Knative. Runs isolated extraction "
            "workers with automatic scaling from 0 to 8 instances. Ideal for high-throughput "
            "frame slicing and GIF transcoding without consuming local CPU or RAM."
        ),
        "target_service": "Cloud Run (Knative)",
        "cpu_shapes": "4 vCPU (Flex Gen2)",
        "memory_tiers": "16 GiB RAM",
        "gpu_options": "NVIDIA L4 24GB (Optional)",
        "cost_estimate": "~$0.09 / hr (Per-second billing)",
        "cold_start": "~1.2s (Gen2 container)",
        "regions": [
            "us-central1 (Iowa)",
            "us-east1 (S. Carolina)",
            "europe-west1 (Belgium)",
            "asia-east1 (Taiwan)",
        ],
        "config_file": "infra/cloud/gcd/cloud-run-service.yaml",
        "is_poc_target": True,
    },
    {
        "provider_id": "cloudflare",
        "name": "Cloudflare Workers & Queues",
        "badge_text": "Planned / Edge Queue",
        "badge_token": "accent_hover",
        "description": (
            "Ultra-low-latency edge queue consumer backed by Cloudflare R2 bucket storage "
            "and D1 analytics database. Coordinates asynchronous batch jobs across 300+ global PoPs "
            "with instant edge dispatch."
        ),
        "target_service": "Workers + R2 + D1",
        "cpu_shapes": "128 MB V8 Isolate",
        "memory_tiers": "Unmetered Edge I/O",
        "gpu_options": "Cloudflare AI / Partner API",
        "cost_estimate": "$5/mo base + $0.50/M ops",
        "cold_start": "~5ms (V8 Isolate)",
        "regions": ["Global Edge (300+ PoPs)"],
        "config_file": "infra/cloud/cloudflare/wrangler.toml",
        "is_poc_target": False,
    },
    {
        "provider_id": "oracle",
        "name": "Oracle Cloud Infrastructure (OCI)",
        "badge_text": "Planned / GPU Shapes",
        "badge_token": "accent",
        "description": (
            "High-performance OCI Container Instances running on AMD E4 or Ampere A1 Flex cores, "
            "with dedicated NVIDIA A10 Tensor Core GPUs available for deep-learning image generation "
            "and heavy parallel workloads."
        ),
        "target_service": "OCI Container Instance",
        "cpu_shapes": "4 OCPU (8 vCPU)",
        "memory_tiers": "16–64 GiB RAM",
        "gpu_options": "NVIDIA A10 24GB Tensor Core",
        "cost_estimate": "Always Free Tier / ~$0.05/hr",
        "cold_start": "~3–5s (OCI Container)",
        "regions": [
            "us-ashburn-1 (N. Virginia)",
            "us-phoenix-1 (Arizona)",
            "eu-frankfurt-1 (Germany)",
        ],
        "config_file": "infra/cloud/oracle/oci-container-instance.tf",
        "is_poc_target": False,
    },
    {
        "provider_id": "aws",
        "name": "Amazon Web Services (AWS)",
        "badge_text": "Roadmap / Fargate",
        "badge_token": "muted_text",
        "description": (
            "Serverless container execution on AWS Fargate with S3 results storage "
            "and SQS asynchronous job queuing."
        ),
        "target_service": "Fargate / ECS + S3",
        "cpu_shapes": "4 vCPU",
        "memory_tiers": "16 GiB RAM",
        "gpu_options": "AWS G5 / G6e Instances",
        "cost_estimate": "~$0.16 / hr",
        "cold_start": "~10–15s (Fargate task)",
        "regions": [
            "us-east-1 (N. Virginia)",
            "us-west-2 (Oregon)",
            "eu-west-1 (Ireland)",
        ],
        "config_file": "infra/cloud/aws/cfn-template.yaml",
        "is_poc_target": False,
    },
]

_PROVIDERS_BY_ID = {provider["provider_id"]: provider for provider in _PROVIDER_CATALOG}


def providers_result() -> dict[str, Any]:
    """Bridge payload for ``cloud_setup.providers``."""
    return {"providers": [dict(provider) for provider in _PROVIDER_CATALOG]}


def provider_ids() -> list[str]:
    """The catalog order, for validation and tests."""
    return [provider["provider_id"] for provider in _PROVIDER_CATALOG]


def is_provider(provider_id: str) -> bool:
    return provider_id in _PROVIDERS_BY_ID


__all__ = [
    "is_provider",
    "provider_ids",
    "providers_result",
]
