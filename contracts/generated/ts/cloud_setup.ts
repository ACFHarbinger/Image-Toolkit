// GENERATED — contract hash 11d82ceaf8037efde28126d5553743180fc68a3cda0403f18d9fb8b764f6b3df. Do not edit; edit the schema and regenerate.

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
