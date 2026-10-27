// GENERATED — contract hash 169175762b264adb9d36a696a336f271756697110ca9654fd44b5bb0eb9ffe1b. Do not edit; edit the schema and regenerate.

export interface PrefsDescribeParams {
  readonly account: string;
}
export interface PrefsDescribeResult {
  readonly sections: Array<"appearance" | "profiles" | "shortcuts" | "tab_config" | "credentials" | "reset">;
  readonly credentials_changed: false;
  readonly reason: "credentials stay on the C++ vault session";
}
