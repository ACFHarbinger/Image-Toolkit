// GENERATED — contract hash e98d26c96ac04681cd010af6b6d27aa2803c65965ba50e9301fa967f227459dd. Do not edit; edit the schema and regenerate.

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
