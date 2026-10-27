// GENERATED — contract hash a4f0fd0f3b4e540630dddc3eaec3ec0e11e1e32419cff02dda892fb79373d8d4. Do not edit; edit the schema and regenerate.

export type CloudSetupEmptyParams = Record<string, unknown>;
export interface ProviderDescriptor {
  readonly provider_id: "gcd" | "cloudflare" | "oracle" | "aws";
  readonly name: string;
  readonly badge_text: string;
  readonly badge_token: string;
  readonly description: string;
  readonly target_service: string;
  readonly cpu_shapes: string;
  readonly memory_tiers: string;
  readonly gpu_options: string;
  readonly cost_estimate: string;
  readonly cold_start: string;
  readonly regions: Array<string>;
  readonly config_file?: string;
  readonly is_poc_target: boolean;
}
export interface ProvidersResult {
  readonly providers: Array<ProviderDescriptor>;
}
