// GENERATED — contract hash ea722120ad8fa351bac3b321f84c91a7ef6452903f1eab7771fe53292a7ece8f. Do not edit; edit the schema and regenerate.

export interface PrefsDescribeParams {
  readonly account: string;
}
export interface PrefsDescribeResult {
  readonly sections: Array<"appearance" | "profiles" | "shortcuts" | "tab_config" | "credentials" | "reset">;
  readonly credentials_changed: false;
  readonly reason: "credentials stay on the C++ vault session";
}
