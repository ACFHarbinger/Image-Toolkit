// GENERATED — contract hash 6a45b8f32749068100d96710e9ad83f596745d32b6cb9702fc61e1997c228ea4. Do not edit; edit the schema and regenerate.

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
