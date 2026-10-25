// GENERATED — contract hash 08faec06515d9a8705e5ee5589a1933a46e3091792150fb9145b7bdb772a2acb. Do not edit; edit the schema and regenerate.
// `const` fields degrade to their scalar type; the framing layer (#875)
// enforces exact values.

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DaemonStatus {
    pub lease_owner: String,
    pub wal_depth: i64,
    pub last_poll_ts: f64,
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

pub type SummaryParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SummaryResult {
    pub running: i64,
    pub reserved_usd: f64,
    pub available: bool,
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
