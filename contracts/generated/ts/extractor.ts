// GENERATED — contract hash 5d09c62e96add841a446e510377b41502c35f696efd20917e72d8df65160033d. Do not edit; edit the schema and regenerate.

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
