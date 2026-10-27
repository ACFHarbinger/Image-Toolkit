// GENERATED — contract hash 3624089fd7d9b561e8900f0d7db9e39da11aa994b2d92e7cbee47cd74baee130. Do not edit; edit the schema and regenerate.

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
