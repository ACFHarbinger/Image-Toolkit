// GENERATED — contract hash 7f853bd58530640761fee9a62783e191b67b9cbc62db9153cfadfc7c15d42687. Do not edit; edit the schema and regenerate.

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
