# GENERATED — contract hash 1b61179c45bf104ff11ace0dc1d0236da1e1e7b9c540fb808333f24757910a89. Do not edit; edit the schema and regenerate.
"""Generated bridge-contract types. Typing-only: boundary validation of
envelopes is the bridge package's job (#875).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Literal

@dataclass(frozen=True)
class CloudSubmitParams:
    spec: JobSpecDocument
    acknowledged: list[str]


@dataclass(frozen=True)
class CloudSubmitResult:
    accepted: bool
    job_id: str
    reason: str


@dataclass(frozen=True)
class DaemonStatus:
    lease_owner: str
    wal_depth: int
    last_poll_ts: float


@dataclass(frozen=True)
class EstimateBreakdown:
    compute: float
    startup: float
    ipv4: float
    storage: float
    egress: float
    retries: float
    total: float


@dataclass(frozen=True)
class JobDetailParams:
    job_id: str


@dataclass(frozen=True)
class JobDetailResult:
    job_id: str
    kind: str
    title: str
    state: str
    provider: str
    created_at: float
    events: list[JobEventItem]
    outputs: list[str]
    logs: list[str]
    metrics: JobMetrics
    spend: JobSpend
    daemon_status: DaemonStatus
    started_at: (float | None) | None = None
    ended_at: (float | None) | None = None


@dataclass(frozen=True)
class JobEventItem:
    id: int
    ts: float
    type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class JobMetrics:
    gpu_util_pct: float
    vram_used_mb: float
    peak_vcpu: float


@dataclass(frozen=True)
class JobSpend:
    cost_so_far_usd: float
    reserved_usd: float
    max_spend_usd: float


@dataclass(frozen=True)
class JobSummaryItem:
    job_id: str
    kind: str
    title: str
    state: str
    provider: str
    created_at: float
    cost_usd: float
    shards_total: int
    shards_done: int
    started_at: (float | None) | None = None
    ended_at: (float | None) | None = None


@dataclass(frozen=True)
class ListJobsParams:
    state: str | None = None
    provider: str | None = None
    kind: str | None = None
    search: str | None = None
    limit: int | None = None


@dataclass(frozen=True)
class ListJobsResult:
    jobs: list[JobSummaryItem]


@dataclass(frozen=True)
class PreviewIssue:
    stage: str
    severity: str
    message: str
    ack_id: str | None
    targets: list[str]


@dataclass(frozen=True)
class PreviewParams:
    spec: JobSpecDocument


@dataclass(frozen=True)
class PreviewResult:
    available: bool
    reason: str
    job_id: str
    kind: str
    provider: str
    region: str
    mode: str
    storage: str
    data_class: str
    shards: int
    staging_bytes: int
    estimate_known: bool
    estimate: EstimateBreakdown
    price_age_days: int | None
    issues: list[PreviewIssue]
    needs_ack: list[str]
    capability_override: bool


@dataclass(frozen=True)
class ResourceRow:
    provider: str
    kind: str
    resource_id: str
    region: str
    job_id: str
    orphan: bool


@dataclass(frozen=True)
class ResourcesResult:
    available: bool
    resources: list[ResourceRow]


@dataclass(frozen=True)
class SpendByProvider:
    provider: str
    actual_usd: float


@dataclass(frozen=True)
class SpendResult:
    available: bool
    month_actual_usd: float
    reserved_usd: float
    by_provider: list[SpendByProvider]


@dataclass(frozen=True)
class SummaryResult:
    running: int
    reserved_usd: float
    available: bool


@dataclass(frozen=True)
class TerminateParams:
    resource_id: str


@dataclass(frozen=True)
class TerminateResult:
    accepted: bool
    resource_id: str
    reason: str


@dataclass(frozen=True)
class PrefillParams:
    owner: str
    estimated_gb: float
    device_gb: float


@dataclass(frozen=True)
class PrefillResult:
    offered: bool
    submitted: Literal[False]
    reason: str
    estimate_usd: float
    estimate_known: bool
    kind: str
    vram_gb_min: float
    provider: str
    region: str
    runtime_s: float
    job_id: str
    spec: dict[str, Any]


@dataclass(frozen=True)
class ConvertBatchParams:
    input_dir: str
    output_dir: str
    output_format: str | None = None
    input_formats: (list[str]) | None = None
    quality: Literal[95] | None = None
    recursive: bool | None = None
    overwrite: bool | None = None


@dataclass(frozen=True)
class ConvertBatchResult:
    job_id: str


@dataclass(frozen=True)
class ConvertParams:
    input_path: str
    output_path: str
    output_format: str | None = None
    quality: Literal[95] | None = None
    overwrite: bool | None = None


@dataclass(frozen=True)
class ConvertResult:
    input_path: str
    output_path: str
    success: bool
    size_bytes: int | None = None
    elapsed_seconds: float | None = None
    error: (str | None) | None = None


@dataclass(frozen=True)
class BridgeError:
    code: str
    retryable: bool
    message_key: str
    details: (dict[str, Any]) | None = None


@dataclass(frozen=True)
class BridgeEvent:
    channel: str
    seq: int
    kind: str
    durable: bool
    ts: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CancelParams:
    job_id: str


@dataclass(frozen=True)
class CancelResult:
    ok: Literal[True]


@dataclass(frozen=True)
class JobEventPayload:
    job_id: str
    state: JobState
    progress: JobProgress | None = None


@dataclass(frozen=True)
class JobListSnapshot:
    jobs: list[JobStatus]


@dataclass(frozen=True)
class JobProgress:
    done: int
    total: int


class JobState(str, enum.Enum):
    QUEUED = "queued"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    CANCELLING = "cancelling"
    COLLECTING = "collecting"
    SETTLING = "settling"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CAPPED = "capped"


@dataclass(frozen=True)
class JobStatus:
    job_id: str
    kind: str
    state: JobState
    progress: JobProgress | None = None
    error: BridgeError | None = None
    result: (dict[str, Any]) | None = None


@dataclass(frozen=True)
class ListParams:
    states: (list[JobState]) | None = None
    limit: int | None = None


@dataclass(frozen=True)
class ListResult:
    jobs: list[JobStatus]


@dataclass(frozen=True)
class StatusParams:
    job_id: str


@dataclass(frozen=True)
class SubmitParams:
    kind: str
    spec: dict[str, Any]


@dataclass(frozen=True)
class SubmitResult:
    job_id: str


@dataclass(frozen=True)
class BridgeRequest:
    jsonrpc: Literal["2.0"]
    id: str | int | None
    method: str
    params: (dict[str, Any]) | None = None


@dataclass(frozen=True)
class ErrorResponse:
    jsonrpc: Literal["2.0"]
    id: str | int | None
    error: RpcErrorObject


@dataclass(frozen=True)
class ResultResponse:
    jsonrpc: Literal["2.0"]
    id: str | int | None
    result: dict[str, Any] | list[Any] | str | float | bool | None


@dataclass(frozen=True)
class RpcErrorObject:
    code: int
    message: str
    data: BridgeError


@dataclass(frozen=True)
class SaveMetadataItem:
    path: str
    tags: (list[str]) | None = None
    group_name: (str | None) | None = None
    subgroup_name: (str | None) | None = None


@dataclass(frozen=True)
class SaveMetadataParams:
    items: list[SaveMetadataItem]


@dataclass(frozen=True)
class SaveMetadataResult:
    saved_count: int
    success: bool
    database_available: bool
    errors: (list[str]) | None = None


@dataclass(frozen=True)
class ScanDirectoryParams:
    directory: str
    recursive: bool | None = None
    formats: (list[str]) | None = None
    max_results: int | None = None


@dataclass(frozen=True)
class ScanDirectoryResult:
    directory: str
    total_found: int
    images: list[ScannedImage]
    database_available: bool


@dataclass(frozen=True)
class ScannedImage:
    path: str
    filename: str
    extension: str
    size_bytes: int
    in_database: bool
    width: (int | None) | None = None
    height: (int | None) | None = None
    tags: (list[str]) | None = None
    group_name: (str | None) | None = None
    subgroup_name: (str | None) | None = None


@dataclass(frozen=True)
class SuggestTagsParams:
    paths: list[str]


@dataclass(frozen=True)
class SuggestTagsResult:
    suggestions: dict[str, list[str]]


@dataclass(frozen=True)
class GetManyParams:
    keys: list[str]


@dataclass(frozen=True)
class GetManyResult:
    values: dict[str, Any]


@dataclass(frozen=True)
class GetParams:
    key: str


@dataclass(frozen=True)
class GetResult:
    key: str
    value: None | bool | float | str | list[Any] | dict[str, Any]
    scope: Scope


class Scope(str, enum.Enum):
    DEVICE = "device"
    ACCOUNT = "account"
    SESSION = "session"


@dataclass(frozen=True)
class SetManyParams:
    updates: dict[str, Any]


@dataclass(frozen=True)
class SetManyResult:
    values: dict[str, Any]


@dataclass(frozen=True)
class SetParams:
    key: str
    value: None | bool | float | str | list[Any] | dict[str, Any]


@dataclass(frozen=True)
class SetResult:
    key: str
    value: None | bool | float | str | list[Any] | dict[str, Any]
    scope: Scope


@dataclass(frozen=True)
class BridgeStatePayload:
    state: str


@dataclass(frozen=True)
class BridgeStateSnapshot:
    state: str


@dataclass(frozen=True)
class ClientInfo:
    name: str
    version: str


@dataclass(frozen=True)
class Compatibility:
    min: str
    max: str


@dataclass(frozen=True)
class HandshakeParams:
    protocol: str
    client: ClientInfo


@dataclass(frozen=True)
class HandshakeResult:
    protocol: str
    version: str
    compatibility: Compatibility
    capabilities: list[str]


@dataclass(frozen=True)
class PingResult:
    ok: Literal[True]


JobSpecDocument = dict[str, Any]


ResourcesParams = dict[str, Any]


SpendParams = dict[str, Any]


SummaryParams = dict[str, Any]


BridgeResponse = ResultResponse | ErrorResponse


PingParams = dict[str, Any]
