// GENERATED — contract hash c9b6edf9c60311bf50a4e7d58a6a25d9164f0ceda3a71af6ec8de11344e19fe8. Do not edit; edit the schema and regenerate.

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
  readonly spec: Record<string, unknown>;
}
