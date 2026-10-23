// GENERATED — contract hash 5a4561cc935e5e7098bbb70e673dbe80fcc9da00470d369b67b897593f256ffe. Do not edit; edit the schema and regenerate.

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
export interface TerminateParams {
  readonly resource_id: string;
}
export interface TerminateResult {
  readonly accepted: boolean;
  readonly resource_id: string;
  readonly reason: string;
}
