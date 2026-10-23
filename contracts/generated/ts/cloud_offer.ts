// GENERATED — contract hash 8df3e3c358bb96402c6c835a3701454161463c07b6f8d0517b138016d22ef4a0. Do not edit; edit the schema and regenerate.

export interface PrefillParams {
  readonly owner: string;
  readonly estimated_gb: number;
  readonly device_gb: number;
}
export interface PrefillResult {
  readonly offered: boolean;
  readonly submitted: false;
  readonly reason: string;
  readonly estimate_usd: number;
  readonly estimate_known: boolean;
  readonly kind: string;
  readonly vram_gb_min: number;
  readonly provider: string;
  readonly region: string;
  readonly runtime_s: number;
  readonly job_id: string;
}
