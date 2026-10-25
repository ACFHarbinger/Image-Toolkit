// GENERATED — contract hash 9c3ee12cc3be627bb53d8e6b3f564849a135edb081df72e2492a9981a5782385. Do not edit; edit the schema and regenerate.

export interface DaemonStatus {
  readonly lease_owner: string;
  readonly wal_depth: number;
  readonly last_poll_ts: number;
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
export type SummaryParams = Record<string, unknown>;
export interface SummaryResult {
  readonly running: number;
  readonly reserved_usd: number;
  readonly available: boolean;
}
