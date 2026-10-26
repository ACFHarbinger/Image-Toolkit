// GENERATED — contract hash e0db33d9af5a9a4f1a6cdc08951212bea919fbae41766e4c197dbe507cb15e7e. Do not edit; edit the schema and regenerate.
// `const` fields degrade to their scalar type; the framing layer (#875)
// enforces exact values.

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct AuthStatusParams {
    pub account: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct AuthStatusResult {
    /// must be false (enforced by the framing layer, #875)
    pub unlocked: bool,
    pub account: String,
    /// must be "unlock stays on the C++ session" (enforced by the framing layer, #875)
    pub reason: String,
}

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

pub type CloudSetupEmptyParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProviderDescriptor {
    pub provider_id: String,
    pub name: String,
    pub badge_text: String,
    pub badge_token: String,
    pub description: String,
    pub target_service: String,
    pub cpu_shapes: String,
    pub memory_tiers: String,
    pub gpu_options: String,
    pub cost_estimate: String,
    pub cold_start: String,
    pub regions: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub config_file: Option<String>,
    pub is_poc_target: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProvidersResult {
    pub providers: Vec<ProviderDescriptor>,
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
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub paths: Option<Vec<String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub action: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub width: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub height: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub algorithm: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub video_codec: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audio_codec: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub crf: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConvertBatchResult {
    pub job_id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConvertListDirParams {
    pub directory: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConvertListDirResult {
    pub files: Vec<String>,
    pub error: String,
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
pub struct AuthConfig {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub username: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub api_key: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CrawlParams {
    pub crawler_type: String,
    pub download_dir: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub url: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub tags: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub limit: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_pages: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actions: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub login_config: Option<LoginConfig>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub auth: Option<AuthConfig>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CrawlResult {
    pub success: bool,
    pub crawler_type: String,
    pub total_downloaded: i64,
    pub download_dir: String,
    pub errors: Vec<String>,
    pub elapsed_seconds: f64,
}

pub type CrawlerSupportedParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CrawlerSupportedResult {
    pub types: Vec<String>,
    pub boards: Vec<String>,
    pub action_templates: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct LoginConfig {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub url: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub username: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub password: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ArapDeformParams {
    pub image_path: String,
    pub control_points: Vec<Vec<f64>>,
    pub target_points: Vec<Vec<f64>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub mesh_resolution: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ArapDeformPayload {
    pub success: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_path: Option<serde_json::Value>,
    pub num_vertices: i64,
    pub num_triangles: i64,
    pub elapsed_seconds: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ColorizeReferenceParams {
    pub lineart_path: String,
    pub reference_path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub epsilon: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub max_iter: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ColorizeScribbleParams {
    pub lineart_path: String,
    pub scribble_path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub intensity: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub use_screentone: Option<bool>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ColorizeScribblePayload {
    pub success: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_path: Option<serde_json::Value>,
    pub width: i64,
    pub height: i64,
    pub elapsed_seconds: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PropagateSequenceParams {
    pub frame_paths: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub keyframe_index: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub keyframe_color_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_dir: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PropagateSequencePayload {
    pub success: bool,
    pub output_paths: Vec<String>,
    pub frames_processed: i64,
    pub elapsed_seconds: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct LogsReadParams {
    pub path: String,
    pub limit: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct LogsReadResult {
    pub found: bool,
    pub path: String,
    pub lines: Vec<String>,
    pub error_count: i64,
    pub reason: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct MetadataDescribeParams {
    pub path: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct MetadataDescribeResult {
    pub found: bool,
    pub path: String,
    pub name: String,
    pub size: i64,
    pub suffix: String,
    pub reason: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DlInspectParams {
    pub run_dir: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DlInspectResult {
    pub found: bool,
    pub run_dir: String,
    pub run_id: String,
    pub status: String,
    pub engine: String,
    pub model_id: String,
    pub event_count: i64,
    /// must be false (enforced by the framing layer, #875)
    pub started: bool,
    pub reason: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DriveSyncPlanParams {
    pub provider: String,
    pub paths: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct DriveSyncPlanResult {
    /// must be false (enforced by the framing layer, #875)
    pub submitted: bool,
    pub provider: String,
    pub count: i64,
    pub reason: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EntityReconDescribeResult {
    pub available: bool,
    pub config: ReconConfigSnapshot,
}

pub type EntityReconEmptyParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EntityReconResolveParams {
    pub image_path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub search_scope: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub local_match_threshold: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub top_k: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EntityReconResolveResult {
    pub available: bool,
    pub found: bool,
    pub name: String,
    pub confidence: f64,
    pub method: String,
    pub origin: String,
    pub local_matches: Vec<LocalMatchItem>,
    pub web_domains: Vec<WebDomainItem>,
    pub report: ProvenanceReportItem,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct LocalMatchItem {
    pub label: String,
    pub path: String,
    pub score: f64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProvenanceEntryItem {
    pub kind: String,
    pub label: String,
    pub source: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub domain: Option<String>,
    pub score: f64,
    pub method: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProvenanceReportItem {
    pub query_hash: String,
    pub predicted_name: String,
    pub confidence: f64,
    pub method: String,
    pub created_at: String,
    pub entries: Vec<ProvenanceEntryItem>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ReconConfigSnapshot {
    pub search_scope: String,
    pub privacy_mode: bool,
    pub local_match_threshold: f64,
    pub top_k: i64,
    pub embed_mode: String,
    pub reverse_engines: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct WebDomainItem {
    pub domain: String,
    pub count: i64,
    pub urls: Vec<String>,
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
pub struct ExtractorCutParams {
    pub path: String,
    pub output_dir: String,
    pub arrangement: String,
    pub frame_width: i64,
    pub frame_height: i64,
    pub offset_x: i64,
    pub offset_y: i64,
    pub spacing: i64,
    pub include_partial: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ExtractorJobResult {
    pub job_id: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ExtractorRangeParams {
    pub path: String,
    pub start_seconds: f64,
    pub end_seconds: f64,
    pub output_path: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ExtractorSnapshotParams {
    pub path: String,
    pub time_seconds: f64,
    pub output_path: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProbeParams {
    pub path: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ProbeResult {
    pub available: bool,
    pub path: String,
    pub width: i64,
    pub height: i64,
    pub duration_seconds: f64,
    pub codec: String,
    pub error: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EditParams {
    pub document_id: String,
    pub operation: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub parameters: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EditResult {
    pub success: bool,
    pub document_id: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub output_document_id: Option<serde_json::Value>,
    pub modified_layers: Vec<String>,
    pub elapsed_seconds: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ExportDocumentParams {
    pub document_id: String,
    pub output_path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub format: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub quality: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ExportDocumentResult {
    pub success: bool,
    pub output_path: String,
    pub size_bytes: i64,
    pub elapsed_seconds: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

pub type ListCapabilitiesParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ListCapabilitiesResult {
    pub capabilities: Vec<String>,
    pub models_available: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct OpenDocumentParams {
    pub source: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub document_id: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub metadata: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct OpenDocumentResult {
    pub success: bool,
    pub document_id: String,
    pub frame_count: i64,
    pub width: i64,
    pub height: i64,
    pub elapsed_seconds: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
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
pub struct MediaPlanParams {
    pub url: String,
    pub destination: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct MediaPlanResult {
    pub accepted: bool,
    /// must be false (enforced by the framing layer, #875)
    pub downloaded: bool,
    pub url: String,
    pub destination: String,
    pub reason: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConcatenateParams {
    pub paths: Vec<String>,
    pub output_path: String,
    pub direction: String,
    pub spacing: i64,
    pub align: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ConcatenateResult {
    pub written: bool,
    pub output_path: String,
    pub width: i64,
    pub height: i64,
    pub preview_png_base64: String,
    pub error: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct MergePlaceParams {
    pub placements: Vec<MergePlacement>,
    pub output_path: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct MergePlacement {
    pub path: String,
    pub x: i64,
    pub y: i64,
    pub width: i64,
    pub height: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PrefsDescribeParams {
    pub account: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct PrefsDescribeResult {
    pub sections: Vec<String>,
    /// must be false (enforced by the framing layer, #875)
    pub credentials_changed: bool,
    /// must be "credentials stay on the C++ vault session" (enforced by the framing layer, #875)
    pub reason: String,
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
pub struct EngineRecord {
    pub id: String,
    pub label: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct EnginesResult {
    pub engines: Vec<EngineRecord>,
}

pub type ReverseSearchEmptyParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ReverseSearchResultItem {
    pub url: String,
    pub engine: String,
    pub score: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub resolution: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub title: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SearchParams {
    pub engine: String,
    pub image_path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub limit: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub roi: Option<Vec<i64>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SearchResult {
    pub ok: bool,
    pub engine: String,
    pub results: Vec<ReverseSearchResultItem>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
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
pub struct CompareItem {
    pub path: String,
    pub width: i64,
    pub height: i64,
    pub ahash: String,
    pub error: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ComparePair {
    pub left: String,
    pub right: String,
    pub distance: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CompareParams {
    pub paths: Vec<String>,
    pub threshold: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct CompareResult {
    pub items: Vec<CompareItem>,
    pub pairs: Vec<ComparePair>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SimilarityScanParams {
    pub directory: String,
    pub threshold: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct StitchStatusParams {
    pub route: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct StitchStatusResult {
    pub route: String,
    /// must be false (enforced by the framing layer, #875)
    pub started: bool,
    /// must be "stitch pipeline is not started" (enforced by the framing layer, #875)
    pub reason: String,
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

pub type GetMonitorsParams = std::collections::HashMap<String, serde_json::Value>;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct GetMonitorsResult {
    pub monitors: Vec<MonitorInfo>,
    pub desktop_environment: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct MonitorInfo {
    pub id: String,
    pub name: String,
    pub width: i64,
    pub height: i64,
    pub x: i64,
    pub y: i64,
    pub is_primary: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SetWallpaperParams {
    pub path_map: std::collections::HashMap<String, String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub style: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub monitors: Option<Vec<i64>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub background_color: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SetWallpaperResult {
    pub success: bool,
    pub message: String,
    pub applied_monitors: Vec<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SlideshowConfigParams {
    pub update: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub interval_seconds: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub style: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub monitor_queues: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub current_paths: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SlideshowConfigResult {
    pub interval_seconds: i64,
    pub style: String,
    pub monitor_queues: std::collections::HashMap<String, Vec<String>>,
    pub current_paths: std::collections::HashMap<String, String>,
    pub config_path: String,
    pub running: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SlideshowToggleParams {
    pub running: bool,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SlideshowToggleResult {
    pub running: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pid: Option<serde_json::Value>,
    pub message: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct WallpaperGraphEdge {
    pub source: String,
    pub target: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct WallpaperGraphNode {
    pub id: String,
    pub path: String,
    pub duration_seconds: i64,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct WallpaperGraphParams {
    pub update: bool,
    pub path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub nodes: Option<Vec<WallpaperGraphNode>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub edges: Option<Vec<WallpaperGraphEdge>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub end_behavior: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub end_color: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct WallpaperGraphResult {
    pub path: String,
    pub nodes: Vec<WallpaperGraphNode>,
    pub edges: Vec<WallpaperGraphEdge>,
    pub end_behavior: String,
    pub end_color: String,
    pub error: String,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ActionItem {
    #[serde(rename = "type")]
    pub r#type: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub param: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ExecuteParams {
    pub url: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub method: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub headers: Option<std::collections::HashMap<String, String>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub body: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timeout_seconds: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct ExecuteResult {
    pub url: String,
    pub status_code: i64,
    pub status_text: String,
    pub headers: std::collections::HashMap<String, String>,
    pub content_type: String,
    pub body: String,
    pub duration_ms: f64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct RequestItem {
    #[serde(rename = "type")]
    pub r#type: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub param: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub headers: Option<std::collections::HashMap<String, String>>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SequenceItemResult {
    pub index: i64,
    pub url: String,
    pub method: String,
    pub status_code: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub saved_path: Option<serde_json::Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<serde_json::Value>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SequenceParams {
    pub base_url: String,
    pub requests: Vec<RequestItem>,
    pub actions: Vec<ActionItem>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub timeout_seconds: Option<i64>,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub struct SequenceResult {
    pub status: String,
    pub base_url: String,
    pub total_requests: i64,
    pub completed_requests: i64,
    pub logs: Vec<String>,
    pub items: Vec<SequenceItemResult>,
    pub message: String,
}
