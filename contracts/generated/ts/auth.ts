// GENERATED — contract hash 169175762b264adb9d36a696a336f271756697110ca9654fd44b5bb0eb9ffe1b. Do not edit; edit the schema and regenerate.

export interface AuthLockParams {
  readonly account: string;
}
export interface AuthLockResult {
  readonly success: boolean;
  readonly account: string;
}
export interface AuthStatusParams {
  readonly account: string;
}
export interface AuthStatusResult {
  readonly unlocked: boolean;
  readonly account: string;
  readonly reason: string;
}
export interface AuthUnlockParams {
  readonly account: string;
  readonly password: string;
}
export interface AuthUnlockResult {
  readonly success: boolean;
  readonly account: string;
  readonly message: string;
}
