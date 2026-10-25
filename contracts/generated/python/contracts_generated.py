# GENERATED — contract hash 08faec06515d9a8705e5ee5589a1933a46e3091792150fb9145b7bdb772a2acb. Do not edit; edit the schema and regenerate.
"""Generated bridge-contract types. Typing-only: boundary validation of
envelopes is the bridge package's job (#875).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Literal

@dataclass(frozen=True)
class DaemonStatus:
    lease_owner: str
    wal_depth: int
    last_poll_ts: float


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
class SummaryResult:
    running: int
    reserved_usd: float
    available: bool


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


SummaryParams = dict[str, Any]


BridgeResponse = ResultResponse | ErrorResponse


PingParams = dict[str, Any]
