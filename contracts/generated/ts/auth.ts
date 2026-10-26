// GENERATED — contract hash 518f5fa10208b0ed73cfe7fbbea67d2d0baddbad24edd98e22e685e1522561a0. Do not edit; edit the schema and regenerate.

export interface AuthStatusParams {
  readonly account: string;
}
export interface AuthStatusResult {
  readonly unlocked: false;
  readonly account: string;
  readonly reason: "unlock stays on the C++ session";
}
