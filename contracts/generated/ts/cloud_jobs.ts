// GENERATED — contract hash 6351f82fd45a8c5d6143cf73e3570df6c3d8d70c885f1e2ccfcf5d09f3540f21. Do not edit; edit the schema and regenerate.

export interface CloudSubmitParams {
  readonly spec: JobSpecDocument;
  readonly acknowledged: Array<string>;
}
export interface CloudSubmitResult {
  readonly accepted: boolean;
  readonly job_id: string;
  readonly reason: string;
}
export interface DaemonStatus {
  readonly lease_owner: string;
  readonly wal_depth: number;
  readonly last_poll_ts: number;
}
export interface EstimateBreakdown {
  readonly compute: number;
  readonly startup: number;
  readonly ipv4: number;
  readonly storage: number;
  readonly egress: number;
  readonly retries: number;
  readonly total: number;
}
export interface JobDetailParams {
  readonly job_id: string;
}
export interface JobDetailResult {
  readonly job_id: string;
  readonly kind: string;
  readonly title: string;
  readonly state: string;
  readonly provider: string;
  readonly created_at: number;
  readonly started_at?: number | null;
  readonly ended_at?: number | null;
  readonly events: Array<JobEventItem>;
  readonly outputs: Array<string>;
  readonly logs: Array<string>;
  readonly metrics: JobMetrics;
  readonly spend: JobSpend;
  readonly daemon_status: DaemonStatus;
}
export interface JobEventItem {
  readonly id: number;
  readonly ts: number;
  readonly type: string;
  readonly data: Record<string, unknown>;
}
export interface JobMetrics {
  readonly gpu_util_pct: number;
  readonly vram_used_mb: number;
  readonly peak_vcpu: number;
}
export type JobSpecDocument = Record<string, unknown>;
export interface JobSpend {
  readonly cost_so_far_usd: number;
  readonly reserved_usd: number;
  readonly max_spend_usd: number;
}
export interface JobSummaryItem {
  readonly job_id: string;
  readonly kind: string;
  readonly title: string;
  readonly state: string;
  readonly provider: string;
  readonly created_at: number;
  readonly started_at?: number | null;
  readonly ended_at?: number | null;
  readonly cost_usd: number;
  readonly shards_total: number;
  readonly shards_done: number;
}
export interface ListJobsParams {
  readonly state?: string;
  readonly provider?: string;
  readonly kind?: string;
  readonly search?: string;
  readonly limit?: number;
}
export interface ListJobsResult {
  readonly jobs: Array<JobSummaryItem>;
}
export interface PreviewIssue {
  readonly stage: string;
  readonly severity: string;
  readonly message: string;
  readonly ack_id: string | null;
  readonly targets: Array<string>;
}
export interface PreviewParams {
  readonly spec: JobSpecDocument;
}
export interface PreviewResult {
  readonly available: boolean;
  readonly reason: string;
  readonly job_id: string;
  readonly kind: string;
  readonly provider: string;
  readonly region: string;
  readonly mode: string;
  readonly storage: string;
  readonly data_class: string;
  readonly shards: number;
  readonly staging_bytes: number;
  readonly estimate_known: boolean;
  readonly estimate: EstimateBreakdown;
  readonly price_age_days: number | null;
  readonly issues: Array<PreviewIssue>;
  readonly needs_ack: Array<string>;
  readonly capability_override: boolean;
}
export type SummaryParams = Record<string, unknown>;
export interface SummaryResult {
  readonly running: number;
  readonly reserved_usd: number;
  readonly available: boolean;
}
