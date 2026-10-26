// GENERATED — contract hash 25bb1ff48ee734cd0ab7e3b3a0936c4ad12ee96988058c651d235a1188a48fd3. Do not edit; edit the schema and regenerate.

export interface DlInspectParams {
  readonly run_dir: string;
}
export interface DlInspectResult {
  readonly found: boolean;
  readonly run_dir: string;
  readonly run_id: string;
  readonly status: string;
  readonly engine: string;
  readonly model_id: string;
  readonly event_count: number;
  readonly started: false;
  readonly reason: string;
}
