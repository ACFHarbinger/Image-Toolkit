// GENERATED — contract hash af34b6b15ababc46f3e0add43e55c137e6b0ea67f7546a3fdfe58e02ded46031. Do not edit; edit the schema and regenerate.

export interface ProbeParams {
  readonly path: string;
}
export interface ProbeResult {
  readonly available: boolean;
  readonly path: string;
  readonly width: number;
  readonly height: number;
  readonly duration_seconds: number;
  readonly codec: string;
  readonly error: string;
}
