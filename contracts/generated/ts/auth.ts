// GENERATED — contract hash 11d82ceaf8037efde28126d5553743180fc68a3cda0403f18d9fb8b764f6b3df. Do not edit; edit the schema and regenerate.

export interface AuthStatusParams {
  readonly account: string;
}
export interface AuthStatusResult {
  readonly unlocked: false;
  readonly account: string;
  readonly reason: "unlock stays on the C++ session";
}
