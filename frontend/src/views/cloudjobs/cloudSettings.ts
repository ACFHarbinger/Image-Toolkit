// Cloud Jobs settings document (D5 / #851): the CloudSettings fields the
// sidecar validates. Defaults mirror middleware/src/cloud/settings.py —
// the backend fills them on read, so these are only the form's reset
// point. The rule editor is not here: rules persist in cloud_jobs.db and
// ride the jobs capability when that surface opens.

export interface CloudJobsSettingsDocument {
  estimates_enabled: boolean;
  warnings_enabled: boolean;
  hard_caps_enabled: boolean;
  default_max_runtime_s: number;
  default_max_spend_usd: number;
  monthly_cap_usd: number;
  warn_job_spend_usd: number;
  warn_runtime_s: number;
  warn_egress_gb: number;
  warn_price_age_days: number;
  warn_cap_fraction: number;
  max_concurrent_jobs: number;
  max_concurrent_gpu_instances: number;
  max_reserved_usd: number;
  max_attempts: number;
  fallback_enabled: boolean;
  default_regions: Record<string, string>;
  sensitive_allowlist: string[];
  packing_mode: string;
  share_cache_volumes: boolean;
  history_retention_days: number;
  staged_input_ttl_days: number;
  cache_ttl_days: number;
  cache_budget_gb: number;
  output_retention_days: number;
  notify_desktop: boolean;
  notify_webhook_url: string;
  notify_email: string;
}

export const CLOUD_JOBS_SETTINGS_KEY = "cloud_jobs/settings";

export const PACKING_MODES = [
  { value: "one_to_one", label: "1:1 (one job per instance)" },
  { value: "chained", label: "Sequential chaining (warm instance)" },
  { value: "parallel", label: "Parallel packing (shared instance)" },
] as const;

type ScalarKey = Exclude<keyof CloudJobsSettingsDocument, "default_regions" | "sensitive_allowlist">;

export type Field =
  | { kind: "toggle"; key: ScalarKey; label: string; hint?: string }
  | { kind: "number"; key: ScalarKey; label: string; unit?: string; min?: number; step?: number }
  | { kind: "select"; key: ScalarKey; label: string; options: readonly { value: string; label: string }[] }
  | { kind: "text"; key: ScalarKey; label: string; placeholder?: string }
  | { kind: "list"; key: "sensitive_allowlist"; label: string; hint?: string };

export interface SettingsSection {
  id: string;
  title: string;
  fields: Field[];
}

export const CLOUD_JOBS_SECTIONS: SettingsSection[] = [
  {
    id: "safeguards",
    title: "Safeguards",
    fields: [
      { kind: "toggle", key: "estimates_enabled", label: "Cost estimates" },
      { kind: "toggle", key: "warnings_enabled", label: "Warning thresholds" },
      { kind: "toggle", key: "hard_caps_enabled", label: "Hard caps" },
    ],
  },
  {
    id: "caps",
    title: "Hard caps",
    fields: [
      { kind: "number", key: "default_max_runtime_s", label: "Max runtime per job", unit: "s", min: 1 },
      { kind: "number", key: "default_max_spend_usd", label: "Max spend per job", unit: "USD", min: 0 },
      { kind: "number", key: "monthly_cap_usd", label: "Monthly cap", unit: "USD", min: 0 },
    ],
  },
  {
    id: "thresholds",
    title: "Warning thresholds",
    fields: [
      { kind: "number", key: "warn_job_spend_usd", label: "Job spend warning", unit: "USD", min: 0 },
      { kind: "number", key: "warn_runtime_s", label: "Runtime warning", unit: "s", min: 1 },
      { kind: "number", key: "warn_egress_gb", label: "Egress warning", unit: "GB", min: 0 },
      { kind: "number", key: "warn_price_age_days", label: "Price age warning", unit: "days", min: 0 },
      { kind: "number", key: "warn_cap_fraction", label: "\"Budget at\" fraction", min: 0.01, step: 0.05 },
    ],
  },
  {
    id: "admission",
    title: "Admission caps",
    fields: [
      { kind: "number", key: "max_concurrent_jobs", label: "Concurrent jobs", min: 1 },
      { kind: "number", key: "max_concurrent_gpu_instances", label: "Concurrent GPU instances", min: 1 },
      { kind: "number", key: "max_reserved_usd", label: "Reserved spend", unit: "USD", min: 0 },
    ],
  },
  {
    id: "recovery",
    title: "Recovery",
    fields: [
      { kind: "number", key: "max_attempts", label: "Retry budget (attempts)", min: 1 },
      { kind: "toggle", key: "fallback_enabled", label: "Automatic fallback", hint: "Move the job to the next approved provider/region/GPU" },
    ],
  },
  {
    id: "instances",
    title: "Instances",
    fields: [
      { kind: "select", key: "packing_mode", label: "Instance packing", options: PACKING_MODES },
      { kind: "toggle", key: "share_cache_volumes", label: "Share model cache volumes" },
    ],
  },
  {
    id: "retention",
    title: "Retention",
    fields: [
      { kind: "number", key: "history_retention_days", label: "Job history", unit: "days", min: 0 },
      { kind: "number", key: "staged_input_ttl_days", label: "Staged inputs", unit: "days (0 = delete after collection)", min: 0 },
      { kind: "number", key: "cache_ttl_days", label: "Model caches", unit: "days", min: 0 },
      { kind: "number", key: "cache_budget_gb", label: "Cache storage budget", unit: "GB", min: 0 },
      { kind: "number", key: "output_retention_days", label: "Outputs", unit: "days", min: 0 },
    ],
  },
  {
    id: "notifications",
    title: "Notifications",
    fields: [
      { kind: "toggle", key: "notify_desktop", label: "Desktop notifications" },
      { kind: "text", key: "notify_webhook_url", label: "Webhook sink", placeholder: "https://hooks.example/…" },
      { kind: "text", key: "notify_email", label: "Email sink", placeholder: "you@example.com" },
    ],
  },
  {
    id: "placement",
    title: "Placement",
    fields: [
      { kind: "list", key: "sensitive_allowlist", label: "Sensitive-data providers", hint: "Comma-separated provider ids allowed for sensitive data" },
    ],
  },
];
