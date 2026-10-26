// GENERATED — contract hash d4c2f9f05e94f415f5a6aecc1d7684c3dcd8e9bd27a3076fe28a1c5cfdf5a174. Do not edit; edit the schema and regenerate.

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
