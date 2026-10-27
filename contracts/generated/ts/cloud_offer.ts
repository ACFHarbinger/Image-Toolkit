// GENERATED — contract hash a4f0fd0f3b4e540630dddc3eaec3ec0e11e1e32419cff02dda892fb79373d8d4. Do not edit; edit the schema and regenerate.

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
