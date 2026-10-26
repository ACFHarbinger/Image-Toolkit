// GENERATED — contract hash 653032d8e300ffda76d5ce42c68053ca1c26001221cde7b7e609718d8a3f829a. Do not edit; edit the schema and regenerate.

export interface AuthStatusParams {
  readonly account: string;
}
export interface AuthStatusResult {
  readonly unlocked: false;
  readonly account: string;
  readonly reason: "unlock stays on the C++ session";
}
