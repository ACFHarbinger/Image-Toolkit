import type { PreviewResult } from "../../../../contracts/generated/ts";
import type { RiskDiagnosis, RiskFinding } from "./risk";

/** The confirmation sheet must use the same rule/ack IDs as submit preflight. */
export function previewDiagnosis(preview: PreviewResult): RiskDiagnosis {
  const needsAck = new Set(preview.needs_ack);
  const findings: RiskFinding[] = preview.issues.map((issue, index) => ({
    rule_id: issue.ack_id ?? `${issue.stage}.${index}`,
    kind: "policy",
    severity: issue.severity === "info" || issue.severity === "warn" ? issue.severity : "block",
    message: issue.message,
    targets: issue.targets,
    disables: [],
    requires_ack: issue.ack_id !== null && needsAck.has(issue.ack_id),
  }));
  for (const id of needsAck) {
    if (!findings.some((finding) => finding.rule_id === id)) {
      findings.push({ rule_id: id, kind: "policy", severity: "warn",
        message: `Preflight requires acknowledgment: ${id}`, targets: [], disables: [], requires_ack: true });
    }
  }
  const blocking = findings.filter((finding) => finding.severity === "block");
  return { findings, blocking, needs_ack: [...needsAck], disabled_fields: new Set(),
    ok_to_submit: (acks) => blocking.length === 0 && [...needsAck].every((id) => acks.has(id)),
    for_field: (field) => findings.filter((finding) => finding.targets.includes(field)),
    severity_of: (field) => findings.find((finding) => finding.targets.includes(field))?.severity ?? null };
}
