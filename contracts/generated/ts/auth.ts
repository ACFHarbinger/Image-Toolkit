// GENERATED — contract hash 1b081c15dfb3252eeb7f0209c44d8f0e6d1689dc3d7a36162b2e9c360c9d65cd. Do not edit; edit the schema and regenerate.

export interface AuthStatusParams {
  readonly account: string;
}
export interface AuthStatusResult {
  readonly unlocked: false;
  readonly account: string;
  readonly reason: "unlock stays on the C++ session";
}
