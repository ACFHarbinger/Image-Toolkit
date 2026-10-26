// GENERATED — contract hash 5d09c62e96add841a446e510377b41502c35f696efd20917e72d8df65160033d. Do not edit; edit the schema and regenerate.

export interface PrefsDescribeParams {
  readonly account: string;
}
export interface PrefsDescribeResult {
  readonly sections: Array<"appearance" | "profiles" | "shortcuts" | "tab_config" | "credentials" | "reset">;
  readonly credentials_changed: false;
  readonly reason: "credentials stay on the C++ vault session";
}
