// GENERATED — contract hash 7886a9fb066af0b1778fca0b4bf80c544815754858676745c46d3f584b33e46c. Do not edit; edit the schema and regenerate.

export interface ResourceRow {
  readonly provider: string;
  readonly kind: string;
  readonly resource_id: string;
  readonly region: string;
  readonly job_id: string;
  readonly orphan: boolean;
}
export type ResourcesParams = Record<string, unknown>;
export interface ResourcesResult {
  readonly available: boolean;
  readonly resources: Array<ResourceRow>;
}
export interface SpendByProvider {
  readonly provider: string;
  readonly actual_usd: number;
}
export type SpendParams = Record<string, unknown>;
export interface SpendResult {
  readonly available: boolean;
  readonly month_actual_usd: number;
  readonly reserved_usd: number;
  readonly by_provider: Array<SpendByProvider>;
}
export type SummaryParams = Record<string, unknown>;
export interface SummaryResult {
  readonly running: number;
  readonly reserved_usd: number;
  readonly available: boolean;
}
export interface TerminateParams {
  readonly resource_id: string;
}
export interface TerminateResult {
  readonly accepted: boolean;
  readonly resource_id: string;
  readonly reason: string;
}
