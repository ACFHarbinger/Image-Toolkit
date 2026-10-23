/**
 * Client-side risk rules evaluation and visual feedback (#830, #850).
 *
 * Implements reactive styling signals (recolouring by severity, bright ⚠ warning
 * messages, and greying out disabled options) matching the backend risk engine.
 */

import { JobSpec, RESUMABLE_KINDS, validateJobSpec } from "./jobSpec";

export type Severity = "info" | "warn" | "block";
export type RuleKind = "capability" | "policy";

export interface RiskFinding {
  rule_id: string;
  kind: RuleKind;
  severity: Severity;
  message: string;
  targets: string[];
  disables: string[];
  requires_ack: boolean;
  capability_override?: boolean;
}

export interface RiskDiagnosis {
  findings: RiskFinding[];
  blocking: RiskFinding[];
  needs_ack: string[];
  disabled_fields: Set<string>;
  ok_to_submit: (acks: Set<string>) => boolean;
  for_field: (field: string) => RiskFinding[];
  severity_of: (field: string) => Severity | null;
}

export interface RiskOptions {
  sensitiveAllowlist?: string[];
  defaultRegions?: Record<string, string>;
  monthToDateUsd?: number;
  monthlyCapUsd?: number;
  cpuOnlyModes?: string[];
}

const DEFAULT_ALLOWLIST = ["gcp", "aws", "azure"];
const DEFAULT_REGIONS: Record<string, string> = {
  runpod: "us-central1",
  gcp: "us-central1",
  aws: "us-east-1",
  azure: "eastus",
  hyperstack: "norway-1",
};

export function evaluateRisk(spec: JobSpec, options?: RiskOptions): RiskDiagnosis {
  const findings: RiskFinding[] = [];
  const allowlist = options?.sensitiveAllowlist ?? DEFAULT_ALLOWLIST;
  const defRegions = options?.defaultRegions ?? DEFAULT_REGIONS;
  const monthlyCap = options?.monthlyCapUsd ?? 50.0;
  const mtd = options?.monthToDateUsd ?? 0.0;

  // 1. Validation checks
  const valErrors = validateJobSpec(spec);
  for (const err of valErrors) {
    findings.push({
      rule_id: "val.invalid_spec",
      kind: "policy",
      severity: "block",
      message: err,
      targets: ["shards", "limits.max_runtime_s", "limits.max_spend_usd", "image"],
      disables: [],
      requires_ack: false,
    });
  }

  // 2. Sensitive data policy
  if (spec.data_class === "sensitive" && !allowlist.includes(spec.placement.provider.toLowerCase())) {
    findings.push({
      rule_id: "sec.sensitive_allowlist",
      kind: "policy",
      severity: "block",
      message: `Sensitive data class cannot be dispatched to non-allowlisted provider '${spec.placement.provider}'.`,
      targets: ["placement.provider", "data_class"],
      disables: [],
      requires_ack: false,
    });
  }

  // 3. Spot instance policy (only resumable workloads like lora_train should use spot)
  const isResumable = RESUMABLE_KINDS.has(spec.kind);
  if (spec.limits.spot_allowed && !isResumable) {
    findings.push({
      rule_id: "safeguard.spot_unresumable",
      kind: "policy",
      severity: "warn",
      message: `Workload kind '${spec.kind}' cannot resume checkpoints. Spot interruptions will cause full loss of in-flight progress.`,
      targets: ["limits.spot_allowed"],
      disables: [],
      requires_ack: true,
    });
  }

  // 4. Monthly budget cap policy
  const estSpend = spec.limits.max_spend_usd ?? 0.0;
  if (mtd + estSpend > monthlyCap) {
    findings.push({
      rule_id: "budget.monthly_cap_exceeded",
      kind: "policy",
      severity: "warn",
      message: `Projected spend ($${(mtd + estSpend).toFixed(2)}) exceeds monthly cap of $${monthlyCap.toFixed(2)}.`,
      targets: ["limits.max_spend_usd"],
      disables: [],
      requires_ack: true,
    });
  }

  // 5. Cross-region data egress warning
  const defRegion = defRegions[spec.placement.provider.toLowerCase()] ?? "us-central1";
  if (spec.placement.region && spec.placement.region !== defRegion) {
    findings.push({
      rule_id: "network.cross_region_egress",
      kind: "policy",
      severity: "info",
      message: `Region '${spec.placement.region}' differs from account primary '${defRegion}'. Cross-region data transfer fees apply.`,
      targets: ["placement.region"],
      disables: [],
      requires_ack: false,
    });
  }

  // 6. Capability checks: GPU requirements
  const needsGpu = spec.resources.gpu_count > 0 || !!spec.resources.gpu_class;
  if (needsGpu && spec.placement.mode === "managed_batch" && spec.placement.provider === "azure") {
    findings.push({
      rule_id: "cap.gpu_mode_unsupported",
      kind: "capability",
      severity: "block",
      message: "GPU workloads are not supported under Azure managed_batch mode.",
      targets: ["resources.gpu_class", "placement.mode"],
      disables: ["placement.mode"],
      requires_ack: false,
    });
  }

  const blocking = findings.filter((f) => f.severity === "block");
  const needs_ack = findings.filter((f) => f.requires_ack).map((f) => f.rule_id);
  const disabled_fields = new Set<string>(findings.flatMap((f) => f.disables));

  return {
    findings,
    blocking,
    needs_ack,
    disabled_fields,
    ok_to_submit: (acks: Set<string>) => {
      if (blocking.length > 0) return false;
      return needs_ack.every((ack) => acks.has(ack));
    },
    for_field: (field: string) => findings.filter((f) => f.targets.includes(field) || f.disables.includes(field)),
    severity_of: (field: string) => {
      const fieldFindings = findings.filter((f) => f.targets.includes(field));
      if (fieldFindings.some((f) => f.severity === "block")) return "block";
      if (fieldFindings.some((f) => f.severity === "warn")) return "warn";
      if (fieldFindings.some((f) => f.severity === "info")) return "info";
      return null;
    },
  };
}

/**
 * Returns Tailwind class styling recolouring field backgrounds and borders by risk level.
 */
export function getRiskInputClass(severity: Severity | null): string {
  switch (severity) {
    case "block":
      return "border-red-500 bg-red-50 text-red-900 focus:border-red-600 focus:ring-red-500 dark:border-red-600 dark:bg-red-950/40 dark:text-red-100";
    case "warn":
      return "border-amber-500 bg-amber-50 text-amber-900 focus:border-amber-600 focus:ring-amber-500 dark:border-amber-600 dark:bg-amber-950/40 dark:text-amber-100";
    case "info":
      return "border-blue-400 bg-blue-50 text-blue-900 focus:border-blue-500 focus:ring-blue-500 dark:border-blue-500 dark:bg-blue-950/40 dark:text-blue-100";
    default:
      return "border-gray-300 bg-white text-gray-900 focus:border-indigo-500 focus:ring-indigo-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100";
  }
}

/**
 * Returns styling classes for prominent ⚠ risk feedback notices.
 */
export function getRiskBannerClass(severity: Severity): string {
  switch (severity) {
    case "block":
      return "bg-red-100 border-red-500 text-red-800 dark:bg-red-950/60 dark:border-red-700 dark:text-red-200";
    case "warn":
      return "bg-amber-100 border-amber-500 text-amber-800 dark:bg-amber-950/60 dark:border-amber-700 dark:text-amber-200";
    case "info":
      return "bg-blue-100 border-blue-400 text-blue-800 dark:bg-blue-950/60 dark:border-blue-700 dark:text-blue-200";
  }
}
