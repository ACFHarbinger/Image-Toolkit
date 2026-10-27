// GENERATED — contract hash 0f49aea8dd625fc56b2e2aaefc29f91d6c8e55ea3e9a57354a03e5352c6ad9b5. Do not edit; edit the schema and regenerate.

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
