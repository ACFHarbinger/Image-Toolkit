// GENERATED — contract hash 25bb1ff48ee734cd0ab7e3b3a0936c4ad12ee96988058c651d235a1188a48fd3. Do not edit; edit the schema and regenerate.

export interface PrefsDescribeParams {
  readonly account: string;
}
export interface PrefsDescribeResult {
  readonly sections: Array<"appearance" | "profiles" | "shortcuts" | "tab_config" | "credentials" | "reset">;
  readonly credentials_changed: false;
  readonly reason: "credentials stay on the C++ vault session";
}
