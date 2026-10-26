# GENERATED — contract hash e0db33d9af5a9a4f1a6cdc08951212bea919fbae41766e4c197dbe507cb15e7e. Do not edit; edit the schema and regenerate.
"""Generated bridge-contract types. Typing-only: boundary validation of
envelopes is the bridge package's job (#875).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Literal

@dataclass(frozen=True)
class AuthStatusParams:
    account: str


@dataclass(frozen=True)
class AuthStatusResult:
    unlocked: Literal[False]
    account: str
    reason: Literal["unlock stays on the C++ session"]


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
class ProviderDescriptor:
    provider_id: str
    name: str
    badge_text: str
    badge_token: str
    description: str
    target_service: str
    cpu_shapes: str
    memory_tiers: str
    gpu_options: str
    cost_estimate: str
    cold_start: str
    regions: list[str]
    is_poc_target: bool
    config_file: str | None = None


@dataclass(frozen=True)
class ProvidersResult:
    providers: list[ProviderDescriptor]


@dataclass(frozen=True)
class ConvertBatchParams:
    input_dir: str
    output_dir: str
    output_format: str | None = None
    input_formats: (list[str]) | None = None
    quality: Literal[95] | None = None
    recursive: bool | None = None
    overwrite: bool | None = None
    paths: (list[str]) | None = None
    action: str | None = None
    width: int | None = None
    height: int | None = None
    algorithm: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    crf: int | None = None


@dataclass(frozen=True)
class ConvertBatchResult:
    job_id: str


@dataclass(frozen=True)
class ConvertListDirParams:
    directory: str


@dataclass(frozen=True)
class ConvertListDirResult:
    files: list[str]
    error: str


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
class AuthConfig:
    username: (str | None) | None = None
    api_key: (str | None) | None = None


@dataclass(frozen=True)
class CrawlParams:
    crawler_type: str
    download_dir: str
    url: (str | None) | None = None
    tags: (str | None) | None = None
    limit: (int | None) | None = None
    max_pages: (int | None) | None = None
    actions: (list[str] | None) | None = None
    login_config: LoginConfig | None = None
    auth: AuthConfig | None = None


@dataclass(frozen=True)
class CrawlResult:
    success: bool
    crawler_type: str
    total_downloaded: int
    download_dir: str
    errors: list[str]
    elapsed_seconds: float


@dataclass(frozen=True)
class CrawlerSupportedResult:
    types: list[str]
    boards: list[str]
    action_templates: list[str]


@dataclass(frozen=True)
class LoginConfig:
    url: (str | None) | None = None
    username: (str | None) | None = None
    password: (str | None) | None = None


@dataclass(frozen=True)
class ArapDeformParams:
    image_path: str
    control_points: list[list[float]]
    target_points: list[list[float]]
    output_path: str | None = None
    mesh_resolution: int | None = None


@dataclass(frozen=True)
class ArapDeformPayload:
    success: bool
    num_vertices: int
    num_triangles: int
    elapsed_seconds: float
    output_path: (str | None) | None = None
    error: (str | None) | None = None


@dataclass(frozen=True)
class ColorizeReferenceParams:
    lineart_path: str
    reference_path: str
    output_path: str | None = None
    epsilon: float | None = None
    max_iter: int | None = None


@dataclass(frozen=True)
class ColorizeScribbleParams:
    lineart_path: str
    scribble_path: str
    output_path: str | None = None
    intensity: float | None = None
    use_screentone: bool | None = None


@dataclass(frozen=True)
class ColorizeScribblePayload:
    success: bool
    width: int
    height: int
    elapsed_seconds: float
    output_path: (str | None) | None = None
    error: (str | None) | None = None


@dataclass(frozen=True)
class PropagateSequenceParams:
    frame_paths: list[str]
    keyframe_index: int | None = None
    keyframe_color_path: str | None = None
    output_dir: str | None = None


@dataclass(frozen=True)
class PropagateSequencePayload:
    success: bool
    output_paths: list[str]
    frames_processed: int
    elapsed_seconds: float
    error: (str | None) | None = None


@dataclass(frozen=True)
class LogsReadParams:
    path: str
    limit: int


@dataclass(frozen=True)
class LogsReadResult:
    found: bool
    path: str
    lines: list[str]
    error_count: int
    reason: str


@dataclass(frozen=True)
class MetadataDescribeParams:
    path: str


@dataclass(frozen=True)
class MetadataDescribeResult:
    found: bool
    path: str
    name: str
    size: int
    suffix: str
    reason: str


@dataclass(frozen=True)
class DlInspectParams:
    run_dir: str


@dataclass(frozen=True)
class DlInspectResult:
    found: bool
    run_dir: str
    run_id: str
    status: str
    engine: str
    model_id: str
    event_count: int
    started: Literal[False]
    reason: str


@dataclass(frozen=True)
class DriveSyncPlanParams:
    provider: str
    paths: list[str]


@dataclass(frozen=True)
class DriveSyncPlanResult:
    submitted: Literal[False]
    provider: str
    count: int
    reason: str


@dataclass(frozen=True)
class EntityReconDescribeResult:
    available: bool
    config: ReconConfigSnapshot


@dataclass(frozen=True)
class EntityReconResolveParams:
    image_path: str
    search_scope: str | None = None
    local_match_threshold: float | None = None
    top_k: int | None = None


@dataclass(frozen=True)
class EntityReconResolveResult:
    available: bool
    found: bool
    name: str
    confidence: float
    method: str
    origin: str
    local_matches: list[LocalMatchItem]
    web_domains: list[WebDomainItem]
    report: ProvenanceReportItem
    error: (str | None) | None = None


@dataclass(frozen=True)
class LocalMatchItem:
    label: str
    path: str
    score: float


@dataclass(frozen=True)
class ProvenanceEntryItem:
    kind: str
    label: str
    source: str
    score: float
    method: str
    domain: str | None = None


@dataclass(frozen=True)
class ProvenanceReportItem:
    query_hash: str
    predicted_name: str
    confidence: float
    method: str
    created_at: str
    entries: list[ProvenanceEntryItem]


@dataclass(frozen=True)
class ReconConfigSnapshot:
    search_scope: str
    privacy_mode: bool
    local_match_threshold: float
    top_k: int
    embed_mode: str
    reverse_engines: list[str]


@dataclass(frozen=True)
class WebDomainItem:
    domain: str
    count: int
    urls: list[str]


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
class ExtractorCutParams:
    path: str
    output_dir: str
    arrangement: str
    frame_width: int
    frame_height: int
    offset_x: int
    offset_y: int
    spacing: int
    include_partial: bool


@dataclass(frozen=True)
class ExtractorJobResult:
    job_id: str


@dataclass(frozen=True)
class ExtractorRangeParams:
    path: str
    start_seconds: float
    end_seconds: float
    output_path: str


@dataclass(frozen=True)
class ExtractorSnapshotParams:
    path: str
    time_seconds: float
    output_path: str


@dataclass(frozen=True)
class ProbeParams:
    path: str


@dataclass(frozen=True)
class ProbeResult:
    available: bool
    path: str
    width: int
    height: int
    duration_seconds: float
    codec: str
    error: str


@dataclass(frozen=True)
class EditParams:
    document_id: str
    operation: str
    parameters: (dict[str, Any] | None) | None = None


@dataclass(frozen=True)
class EditResult:
    success: bool
    document_id: str
    modified_layers: list[str]
    elapsed_seconds: float
    output_document_id: (str | None) | None = None
    error: (str | None) | None = None


@dataclass(frozen=True)
class ExportDocumentParams:
    document_id: str
    output_path: str
    format: (str | None) | None = None
    quality: (int | None) | None = None


@dataclass(frozen=True)
class ExportDocumentResult:
    success: bool
    output_path: str
    size_bytes: int
    elapsed_seconds: float
    error: (str | None) | None = None


@dataclass(frozen=True)
class ListCapabilitiesResult:
    capabilities: list[str]
    models_available: list[str]
    error: (str | None) | None = None


@dataclass(frozen=True)
class OpenDocumentParams:
    source: str
    document_id: (str | None) | None = None
    metadata: (dict[str, Any] | None) | None = None


@dataclass(frozen=True)
class OpenDocumentResult:
    success: bool
    document_id: str
    frame_count: int
    width: int
    height: int
    elapsed_seconds: float
    error: (str | None) | None = None


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
class MediaPlanParams:
    url: str
    destination: str


@dataclass(frozen=True)
class MediaPlanResult:
    accepted: bool
    downloaded: Literal[False]
    url: str
    destination: str
    reason: str


@dataclass(frozen=True)
class ConcatenateParams:
    paths: list[str]
    output_path: str
    direction: str
    spacing: int
    align: str


@dataclass(frozen=True)
class ConcatenateResult:
    written: bool
    output_path: str
    width: int
    height: int
    preview_png_base64: str
    error: str


@dataclass(frozen=True)
class MergePlaceParams:
    placements: list[MergePlacement]
    output_path: str


@dataclass(frozen=True)
class MergePlacement:
    path: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class PrefsDescribeParams:
    account: str


@dataclass(frozen=True)
class PrefsDescribeResult:
    sections: list[str]
    credentials_changed: Literal[False]
    reason: Literal["credentials stay on the C++ vault session"]


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
class EngineRecord:
    id: str
    label: str


@dataclass(frozen=True)
class EnginesResult:
    engines: list[EngineRecord]


@dataclass(frozen=True)
class ReverseSearchResultItem:
    url: str
    engine: str
    score: float
    resolution: str | None = None
    title: (str | None) | None = None


@dataclass(frozen=True)
class SearchParams:
    engine: str
    image_path: str
    limit: int | None = None
    roi: (list[int]) | None = None


@dataclass(frozen=True)
class SearchResult:
    ok: bool
    engine: str
    results: list[ReverseSearchResultItem]
    error: (str | None) | None = None


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
class CompareItem:
    path: str
    width: int
    height: int
    ahash: str
    error: str


@dataclass(frozen=True)
class ComparePair:
    left: str
    right: str
    distance: int


@dataclass(frozen=True)
class CompareParams:
    paths: list[str]
    threshold: int


@dataclass(frozen=True)
class CompareResult:
    items: list[CompareItem]
    pairs: list[ComparePair]


@dataclass(frozen=True)
class SimilarityScanParams:
    directory: str
    threshold: int


@dataclass(frozen=True)
class StitchStatusParams:
    route: str


@dataclass(frozen=True)
class StitchStatusResult:
    route: str
    started: Literal[False]
    reason: Literal["stitch pipeline is not started"]


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


@dataclass(frozen=True)
class GetMonitorsResult:
    monitors: list[MonitorInfo]
    desktop_environment: str


@dataclass(frozen=True)
class MonitorInfo:
    id: str
    name: str
    width: int
    height: int
    x: int
    y: int
    is_primary: bool


@dataclass(frozen=True)
class SetWallpaperParams:
    path_map: dict[str, str]
    style: str | None = None
    monitors: (list[int]) | None = None
    background_color: (str | None) | None = None


@dataclass(frozen=True)
class SetWallpaperResult:
    success: bool
    message: str
    applied_monitors: list[str]


@dataclass(frozen=True)
class SlideshowConfigParams:
    update: bool
    interval_seconds: (int | None) | None = None
    style: (str | None) | None = None
    monitor_queues: (dict[str, list[str]] | None) | None = None
    current_paths: (dict[str, str] | None) | None = None


@dataclass(frozen=True)
class SlideshowConfigResult:
    interval_seconds: int
    style: str
    monitor_queues: dict[str, list[str]]
    current_paths: dict[str, str]
    config_path: str
    running: bool


@dataclass(frozen=True)
class SlideshowToggleParams:
    running: bool


@dataclass(frozen=True)
class SlideshowToggleResult:
    running: bool
    message: str
    pid: (int | None) | None = None


@dataclass(frozen=True)
class WallpaperGraphEdge:
    source: str
    target: str


@dataclass(frozen=True)
class WallpaperGraphNode:
    id: str
    path: str
    duration_seconds: int


@dataclass(frozen=True)
class WallpaperGraphParams:
    update: bool
    path: str
    nodes: (list[WallpaperGraphNode]) | None = None
    edges: (list[WallpaperGraphEdge]) | None = None
    end_behavior: str | None = None
    end_color: str | None = None


@dataclass(frozen=True)
class WallpaperGraphResult:
    path: str
    nodes: list[WallpaperGraphNode]
    edges: list[WallpaperGraphEdge]
    end_behavior: str
    end_color: str
    error: str


@dataclass(frozen=True)
class ActionItem:
    type: str
    param: str | None = None


@dataclass(frozen=True)
class ExecuteParams:
    url: str
    method: str | None = None
    headers: (dict[str, str]) | None = None
    body: str | None = None
    timeout_seconds: int | None = None


@dataclass(frozen=True)
class ExecuteResult:
    url: str
    status_code: int
    status_text: str
    headers: dict[str, str]
    content_type: str
    body: str
    duration_ms: float
    error: (str | None) | None = None


@dataclass(frozen=True)
class RequestItem:
    type: str
    param: str | None = None
    headers: (dict[str, str]) | None = None


@dataclass(frozen=True)
class SequenceItemResult:
    index: int
    url: str
    method: str
    status_code: int
    saved_path: (str | None) | None = None
    error: (str | None) | None = None


@dataclass(frozen=True)
class SequenceParams:
    base_url: str
    requests: list[RequestItem]
    actions: list[ActionItem]
    timeout_seconds: int | None = None


@dataclass(frozen=True)
class SequenceResult:
    status: str
    base_url: str
    total_requests: int
    completed_requests: int
    logs: list[str]
    items: list[SequenceItemResult]
    message: str


JobSpecDocument = dict[str, Any]


ResourcesParams = dict[str, Any]


SpendParams = dict[str, Any]


SummaryParams = dict[str, Any]


CloudSetupEmptyParams = dict[str, Any]


CrawlerSupportedParams = dict[str, Any]


EntityReconEmptyParams = dict[str, Any]


ListCapabilitiesParams = dict[str, Any]


EmptyParams = dict[str, Any]


AdminEmptyParams = dict[str, Any]


BridgeResponse = ResultResponse | ErrorResponse


ReverseSearchEmptyParams = dict[str, Any]


PingParams = dict[str, Any]


GetMonitorsParams = dict[str, Any]
