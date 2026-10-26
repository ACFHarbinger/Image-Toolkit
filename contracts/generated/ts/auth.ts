// GENERATED — contract hash 9fe77d2de0e32c92dfddbdf87c37a1f78a2aa550494a3394c78ad951fd387f08. Do not edit; edit the schema and regenerate.

export interface AuthApplyProfileParams {
  readonly account: string;
  readonly profile: string;
}
export interface AuthApplyProfileResult {
  readonly success: boolean;
  readonly account: string;
  readonly profile: string;
  readonly message: string;
  readonly theme: "dark" | "light";
  readonly tab_configurations: Record<string, unknown>;
}
export interface AuthGuestParams {
  readonly username?: string | null;
}
export interface AuthGuestResult {
  readonly success: boolean;
  readonly account: string;
  readonly anonymous: boolean;
  readonly message: string;
}
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
  readonly profiles?: Array<string>;
  readonly credentials?: Array<string>;
}
