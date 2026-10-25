// GENERATED — contract hash eb57d1d3ee001de50bb35743f515830d8370c51552d7d005103b952116fb1b96. Do not edit; edit the schema and regenerate.

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
