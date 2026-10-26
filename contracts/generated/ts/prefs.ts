// GENERATED — contract hash 653032d8e300ffda76d5ce42c68053ca1c26001221cde7b7e609718d8a3f829a. Do not edit; edit the schema and regenerate.

export interface PrefsDescribeParams {
  readonly account: string;
}
export interface PrefsDescribeResult {
  readonly sections: Array<"appearance" | "profiles" | "shortcuts" | "tab_config" | "credentials" | "reset">;
  readonly credentials_changed: false;
  readonly reason: "credentials stay on the C++ vault session";
}
