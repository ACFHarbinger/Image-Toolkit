// GENERATED — contract hash 518f5fa10208b0ed73cfe7fbbea67d2d0baddbad24edd98e22e685e1522561a0. Do not edit; edit the schema and regenerate.

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
