// GENERATED — contract hash 28918ce8760d36700226684cdf4b39a9465953292b3c3913b49e167c15ce7d55. Do not edit; edit the schema and regenerate.

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
