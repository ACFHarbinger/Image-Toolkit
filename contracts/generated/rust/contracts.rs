// GENERATED — contract hash fd24c10a6c68f14e14dab5faa90a7731cd8aaa7a57489826f7c8836964930567. Do not edit; edit the schema and regenerate.
// `const` fields degrade to their scalar type; the framing layer (#875)
// enforces exact values.

use serde::{Deserialize, Serialize};

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
