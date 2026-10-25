# GENERATED — contract hash 02cbf994e4637ef9eaf9b96f7bc8b6258c31d0f77f66e4fec308264c40cddf06. Do not edit; edit the schema and regenerate.
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
class GroupRecord:
    name: str
    subgroups: list[str]


@dataclass(frozen=True)
class ImageRecord:
    id: int
    file_path: str
    filename: str
    file_size: (int | None) | None = None
    width: (int | None) | None = None
    height: (int | None) | None = None
    phash: (int | None) | None = None
    group_name: (str | None) | None = None
    subgroup_name: (str | None) | None = None
    date_added: (str | None) | None = None
    date_modified: (str | None) | None = None
    tags: (list[str]) | None = None
    distance: (float | None) | None = None


@dataclass(frozen=True)
class ListGroupsResult:
    available: bool
    groups: list[GroupRecord]


@dataclass(frozen=True)
class ListImagesParams:
    group_name: str | None = None
    subgroup_name: str | None = None
    tags: (list[str]) | None = None
    filename_pattern: str | None = None
    input_formats: (list[str]) | None = None
    group_names: (list[str]) | None = None
    subgroup_names: (list[str]) | None = None
    limit: int | None = None


@dataclass(frozen=True)
class ListImagesResult:
    available: bool
    images: list[ImageRecord]


@dataclass(frozen=True)
class ListTagsResult:
    available: bool
    tags: list[str]


@dataclass(frozen=True)
class AdminGroupRecord:
    name: str
    subgroups: list[str]


@dataclass(frozen=True)
class BrowseParams:
    table: str
    limit: int
    offset: int
    column: str | None = None
    equals: str | None = None


@dataclass(frozen=True)
class BrowseResult:
    available: bool
    columns: list[str]
    rows: list[BrowseRow]
    row_count: int
    error: str


@dataclass(frozen=True)
class BrowseRow:
    cells: list[str]


@dataclass(frozen=True)
class CatalogResult:
    available: bool
    groups: list[AdminGroupRecord]
    tags: list[TagRecord]


class MutateAction(str, enum.Enum):
    CREATE_GROUP = "create_group"
    CREATE_SUBGROUP = "create_subgroup"
    CREATE_TAG = "create_tag"
    REMOVE_GROUP = "remove_group"
    REMOVE_SUBGROUP = "remove_subgroup"
    REMOVE_TAG = "remove_tag"
    MERGE_TAGS = "merge_tags"


@dataclass(frozen=True)
class MutateParams:
    action: MutateAction
    name: str
    parent: str | None = None
    category: str | None = None
    destination: str | None = None


@dataclass(frozen=True)
class MutateResult:
    available: bool
    applied: int
    error: str


@dataclass(frozen=True)
class TagRecord:
    name: str
    category: str


@dataclass(frozen=True)
class DescribeItem:
    path: str
    exists: bool
    width: int
    height: int
    animated: bool
    error: str


@dataclass(frozen=True)
class DescribeParams:
    paths: list[str]


@dataclass(frozen=True)
class DescribeResult:
    items: list[DescribeItem]


@dataclass(frozen=True)
class DifferenceParams:
    left: str
    right: str
    boost: str


@dataclass(frozen=True)
class DifferenceResult:
    available: bool
    width: int
    height: int
    mean_abs: float
    reason: str
    png_base64: str


@dataclass(frozen=True)
class FrameParams:
    path: str


@dataclass(frozen=True)
class FrameResult:
    path: str
    width: int
    height: int
    png_base64: str
    error: str


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


EmptyParams = dict[str, Any]


AdminEmptyParams = dict[str, Any]


BridgeResponse = ResultResponse | ErrorResponse


PingParams = dict[str, Any]
