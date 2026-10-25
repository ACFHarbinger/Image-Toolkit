// GENERATED — contract hash 0ddf43995ce7387ccdcb17b3e1810f19002528a099b4e8c2a036122b876a07fb. Do not edit; edit the schema and regenerate.
// `const` fields degrade to their scalar type; the framing layer (#875)
// enforces exact values.

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CloudSubmitParams {
    pub spec: JobSpecDocument,
    pub acknowledged: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CloudSubmitResult {
    pub accepted: bool,
    pub job_id: String,
    pub reason: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DaemonStatus {
    pub lease_owner: String,
    pub wal_depth: i64,
    pub last_poll_ts: f64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EstimateBreakdown {
    pub compute: f64,
    pub startup: f64,
    pub ipv4: f64,
    pub storage: f64,
    pub egress: f64,
    pub retries: f64,
    pub total: f64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobDetailParams {
    pub job_id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobDetailResult {
    pub job_id: String,
    pub kind: String,
    pub title: String,
    pub state: String,
    pub provider: String,
    pub created_at: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub started_at: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ended_at: Option<serde_json::Value>,
    pub events: Vec<JobEventItem>,
    pub outputs: Vec<String>,
    pub logs: Vec<String>,
    pub metrics: JobMetrics,
    pub spend: JobSpend,
    pub daemon_status: DaemonStatus,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobEventItem {
    pub id: i64,
    pub ts: f64,
    #[serde(rename = "type")]
    pub r#type: String,
    pub data: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobMetrics {
    pub gpu_util_pct: f64,
    pub vram_used_mb: f64,
    pub peak_vcpu: f64,
}

pub type JobSpecDocument = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobSpend {
    pub cost_so_far_usd: f64,
    pub reserved_usd: f64,
    pub max_spend_usd: f64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobSummaryItem {
    pub job_id: String,
    pub kind: String,
    pub title: String,
    pub state: String,
    pub provider: String,
    pub created_at: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub started_at: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ended_at: Option<serde_json::Value>,
    pub cost_usd: f64,
    pub shards_total: i64,
    pub shards_done: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListJobsParams {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub state: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub provider: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub kind: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub search: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub limit: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListJobsResult {
    pub jobs: Vec<JobSummaryItem>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PreviewIssue {
    pub stage: String,
    pub severity: String,
    pub message: String,
    pub ack_id: serde_json::Value,
    pub targets: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PreviewParams {
    pub spec: JobSpecDocument,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PreviewResult {
    pub available: bool,
    pub reason: String,
    pub job_id: String,
    pub kind: String,
    pub provider: String,
    pub region: String,
    pub mode: String,
    pub storage: String,
    pub data_class: String,
    pub shards: i64,
    pub staging_bytes: i64,
    pub estimate_known: bool,
    pub estimate: EstimateBreakdown,
    pub price_age_days: serde_json::Value,
    pub issues: Vec<PreviewIssue>,
    pub needs_ack: Vec<String>,
    pub capability_override: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ResourceRow {
    pub provider: String,
    pub kind: String,
    pub resource_id: String,
    pub region: String,
    pub job_id: String,
    pub orphan: bool,
}

pub type ResourcesParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ResourcesResult {
    pub available: bool,
    pub resources: Vec<ResourceRow>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SpendByProvider {
    pub provider: String,
    pub actual_usd: f64,
}

pub type SpendParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SpendResult {
    pub available: bool,
    pub month_actual_usd: f64,
    pub reserved_usd: f64,
    pub by_provider: Vec<SpendByProvider>,
}

pub type SummaryParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SummaryResult {
    pub running: i64,
    pub reserved_usd: f64,
    pub available: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct TerminateParams {
    pub resource_id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct TerminateResult {
    pub accepted: bool,
    pub resource_id: String,
    pub reason: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PrefillParams {
    pub owner: String,
    pub estimated_gb: f64,
    pub device_gb: f64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PrefillResult {
    pub offered: bool,
    /// must be false (enforced by the framing layer, #875)
    pub submitted: bool,
    pub reason: String,
    pub estimate_usd: f64,
    pub estimate_known: bool,
    pub kind: String,
    pub vram_gb_min: f64,
    pub provider: String,
    pub region: String,
    pub runtime_s: f64,
    pub job_id: String,
    pub spec: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConvertBatchParams {
    pub input_dir: String,
    pub output_dir: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_format: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub input_formats: Option<Vec<String>>,
    /// must be 95 (enforced by the framing layer, #875)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub quality: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub recursive: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub overwrite: Option<bool>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConvertBatchResult {
    pub job_id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConvertParams {
    pub input_path: String,
    pub output_path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_format: Option<String>,
    /// must be 95 (enforced by the framing layer, #875)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub quality: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub overwrite: Option<bool>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConvertResult {
    pub input_path: String,
    pub output_path: String,
    pub success: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub size_bytes: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub elapsed_seconds: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct BridgeError {
    pub code: String,
    pub retryable: bool,
    pub message_key: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub details: Option<std::collections::HashMap<String, serde_json::Value>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct BridgeEvent {
    pub channel: String,
    pub seq: i64,
    pub kind: String,
    pub durable: bool,
    pub ts: String,
    pub payload: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CancelParams {
    pub job_id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CancelResult {
    /// must be true (enforced by the framing layer, #875)
    pub ok: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobEventPayload {
    pub job_id: String,
    pub state: JobState,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub progress: Option<JobProgress>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobListSnapshot {
    pub jobs: Vec<JobStatus>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobProgress {
    pub done: i64,
    pub total: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum JobState {
    Queued,
    Provisioning,
    Running,
    Cancelling,
    Collecting,
    Settling,
    Completed,
    Failed,
    Cancelled,
    Capped,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct JobStatus {
    pub job_id: String,
    pub kind: String,
    pub state: JobState,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub progress: Option<JobProgress>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<BridgeError>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<std::collections::HashMap<String, serde_json::Value>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListParams {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub states: Option<Vec<JobState>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub limit: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListResult {
    pub jobs: Vec<JobStatus>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct StatusParams {
    pub job_id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SubmitParams {
    pub kind: String,
    pub spec: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SubmitResult {
    pub job_id: String,
}

pub type EmptyParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct GroupRecord {
    pub name: String,
    pub subgroups: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ImageRecord {
    pub id: i64,
    pub file_path: String,
    pub filename: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub file_size: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub width: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub height: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub phash: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub group_name: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subgroup_name: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub date_added: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub date_modified: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tags: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub distance: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListGroupsResult {
    pub available: bool,
    pub groups: Vec<GroupRecord>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListImagesParams {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub group_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subgroup_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tags: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub filename_pattern: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub input_formats: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub group_names: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subgroup_names: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub limit: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListImagesResult {
    pub available: bool,
    pub images: Vec<ImageRecord>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListTagsResult {
    pub available: bool,
    pub tags: Vec<String>,
}

pub type AdminEmptyParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct AdminGroupRecord {
    pub name: String,
    pub subgroups: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct BrowseParams {
    pub table: String,
    pub limit: i64,
    pub offset: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub column: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub equals: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct BrowseResult {
    pub available: bool,
    pub columns: Vec<String>,
    pub rows: Vec<BrowseRow>,
    pub row_count: i64,
    pub error: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct BrowseRow {
    pub cells: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CatalogResult {
    pub available: bool,
    pub groups: Vec<AdminGroupRecord>,
    pub tags: Vec<TagRecord>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum MutateAction {
    CreateGroup,
    CreateSubgroup,
    CreateTag,
    RemoveGroup,
    RemoveSubgroup,
    RemoveTag,
    MergeTags,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct MutateParams {
    pub action: MutateAction,
    pub name: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parent: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub category: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub destination: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct MutateResult {
    pub available: bool,
    pub applied: i64,
    pub error: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct TagRecord {
    pub name: String,
    pub category: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DescribeItem {
    pub path: String,
    pub exists: bool,
    pub width: i64,
    pub height: i64,
    pub animated: bool,
    pub error: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DescribeParams {
    pub paths: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DescribeResult {
    pub items: Vec<DescribeItem>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DifferenceParams {
    pub left: String,
    pub right: String,
    pub boost: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DifferenceResult {
    pub available: bool,
    pub width: i64,
    pub height: i64,
    pub mean_abs: f64,
    pub reason: String,
    pub png_base64: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct FrameParams {
    pub path: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct FrameResult {
    pub path: String,
    pub width: i64,
    pub height: i64,
    pub png_base64: String,
    pub error: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct BridgeRequest {
    /// must be "2.0" (enforced by the framing layer, #875)
    pub jsonrpc: String,
    pub id: serde_json::Value,
    pub method: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub params: Option<std::collections::HashMap<String, serde_json::Value>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(untagged)]
pub enum BridgeResponse {
    Result(ResultResponse),
    Error(ErrorResponse),
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ErrorResponse {
    /// must be "2.0" (enforced by the framing layer, #875)
    pub jsonrpc: String,
    pub id: serde_json::Value,
    pub error: RpcErrorObject,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ResultResponse {
    /// must be "2.0" (enforced by the framing layer, #875)
    pub jsonrpc: String,
    pub id: serde_json::Value,
    pub result: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct RpcErrorObject {
    pub code: i64,
    pub message: String,
    pub data: BridgeError,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SaveMetadataItem {
    pub path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tags: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub group_name: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subgroup_name: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SaveMetadataParams {
    pub items: Vec<SaveMetadataItem>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SaveMetadataResult {
    pub saved_count: i64,
    pub success: bool,
    pub database_available: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub errors: Option<Vec<String>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ScanDirectoryParams {
    pub directory: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub recursive: Option<bool>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub formats: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_results: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ScanDirectoryResult {
    pub directory: String,
    pub total_found: i64,
    pub images: Vec<ScannedImage>,
    pub database_available: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ScannedImage {
    pub path: String,
    pub filename: String,
    pub extension: String,
    pub size_bytes: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub width: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub height: Option<serde_json::Value>,
    pub in_database: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tags: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub group_name: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub subgroup_name: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SuggestTagsParams {
    pub paths: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SuggestTagsResult {
    pub suggestions: std::collections::HashMap<String, Vec<String>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct GetManyParams {
    pub keys: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct GetManyResult {
    pub values: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct GetParams {
    pub key: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct GetResult {
    pub key: String,
    pub value: serde_json::Value,
    pub scope: Scope,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum Scope {
    Device,
    Account,
    Session,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SetManyParams {
    pub updates: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SetManyResult {
    pub values: std::collections::HashMap<String, serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SetParams {
    pub key: String,
    pub value: serde_json::Value,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SetResult {
    pub key: String,
    pub value: serde_json::Value,
    pub scope: Scope,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct BridgeStatePayload {
    pub state: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct BridgeStateSnapshot {
    pub state: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ClientInfo {
    pub name: String,
    pub version: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct Compatibility {
    pub min: String,
    pub max: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct HandshakeParams {
    pub protocol: String,
    pub client: ClientInfo,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct HandshakeResult {
    pub protocol: String,
    pub version: String,
    pub compatibility: Compatibility,
    pub capabilities: Vec<String>,
}

pub type PingParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PingResult {
    /// must be true (enforced by the framing layer, #875)
    pub ok: bool,
}
