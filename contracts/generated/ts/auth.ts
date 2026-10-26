// GENERATED — contract hash a60d8764530060b4277a430a09842662f494142a594a546bda95b31a575f5262. Do not edit; edit the schema and regenerate.

export interface AuthStatusParams {
  readonly account: string;
}
export interface AuthStatusResult {
  readonly unlocked: false;
  readonly account: string;
  readonly reason: "unlock stays on the C++ session";
}
