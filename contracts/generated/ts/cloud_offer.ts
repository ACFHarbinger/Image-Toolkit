// GENERATED — contract hash a06471e200d0ebbad6b544aa116489d517a985e837bd9bf5c797eb5238e2867d. Do not edit; edit the schema and regenerate.

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
