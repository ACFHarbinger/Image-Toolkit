// GENERATED — contract hash c9734dc6d1b29f88e7c9975cc142965a3f7cdc5c5c907e455625999b987bc515. Do not edit; edit the schema and regenerate.

export interface AuthStatusParams {
  readonly account: string;
}
export interface AuthStatusResult {
  readonly unlocked: false;
  readonly account: string;
  readonly reason: "unlock stays on the C++ session";
}
