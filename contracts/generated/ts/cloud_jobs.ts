// GENERATED — contract hash 1b786b00c07f6a36997bbfb2c4f7587b3fc5c9afdaf805a1a251a13d3b617e85. Do not edit; edit the schema and regenerate.

export interface CloudSubmitParams {
  readonly spec: JobSpecDocument;
  readonly acknowledged: Array<string>;
}
export interface CloudSubmitResult {
  readonly accepted: boolean;
  readonly job_id: string;
  readonly reason: string;
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
export type JobSpecDocument = Record<string, unknown>;
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
