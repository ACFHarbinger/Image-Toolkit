// GENERATED — contract hash 169175762b264adb9d36a696a336f271756697110ca9654fd44b5bb0eb9ffe1b. Do not edit; edit the schema and regenerate.

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
