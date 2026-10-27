// GENERATED — contract hash a4f0fd0f3b4e540630dddc3eaec3ec0e11e1e32419cff02dda892fb79373d8d4. Do not edit; edit the schema and regenerate.

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
