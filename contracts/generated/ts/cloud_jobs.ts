// GENERATED — contract hash 121107d6c8af7ea8eaf2408ee5ee09b85b47ac31aafc0a0cccb660d30457f571. Do not edit; edit the schema and regenerate.

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
