// GENERATED — contract hash fd88a7fef136d55677f1b54786db5f5cc6ad804b203c2f6e41cebc765dabefbd. Do not edit; edit the schema and regenerate.

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
