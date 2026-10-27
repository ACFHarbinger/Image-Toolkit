// GENERATED — contract hash 0f49aea8dd625fc56b2e2aaefc29f91d6c8e55ea3e9a57354a03e5352c6ad9b5. Do not edit; edit the schema and regenerate.

export interface DriveSyncExecuteParams {
  readonly provider: "google_drive" | "dropbox" | "onedrive";
  readonly paths: Array<string>;
  readonly remote_folder?: string;
  readonly dry_run?: boolean;
}
export interface DriveSyncExecuteResult {
  readonly success: boolean;
  readonly provider: "google_drive" | "dropbox" | "onedrive";
  readonly synced_count: number;
  readonly elapsed_seconds: number;
  readonly errors: Array<string>;
}
export interface DriveSyncPlanParams {
  readonly provider: "google_drive" | "dropbox" | "onedrive";
  readonly paths: Array<string>;
}
export interface DriveSyncPlanResult {
  readonly submitted: false;
  readonly provider: "google_drive" | "dropbox" | "onedrive";
  readonly count: number;
  readonly reason: string;
}
