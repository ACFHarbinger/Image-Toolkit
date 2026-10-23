import React, { useState } from "react";
import { formatBytes, formatUsd, JobSpec } from "./jobSpec";
import { getRiskBannerClass, RiskDiagnosis } from "./risk";

export interface PlanCostSheetProps {
  spec: JobSpec;
  diagnosis: RiskDiagnosis;
  onConfirmSubmit: () => Promise<void> | void;
  onClose: () => void;
  isSubmitting?: boolean;
}

export function PlanCostSheet({
  spec,
  diagnosis,
  onConfirmSubmit,
  onClose,
  isSubmitting = false,
}: PlanCostSheetProps): React.ReactElement {
  const [acks, setAcks] = useState<Set<string>>(new Set());

  const toggleAck = (ruleId: string) => {
    setAcks((prev) => {
      const next = new Set(prev);
      if (next.has(ruleId)) {
        next.delete(ruleId);
      } else {
        next.add(ruleId);
      }
      return next;
    });
  };

  const stagingBytes = Object.values(spec.inputs ?? {}).reduce(
    (sum, blob) => sum + (blob.size_bytes || 0),
    0,
  );

  // Compute breakdown estimates
  const computeBase = (spec.limits.max_spend_usd ?? 5.0) * 0.7;
  const startup = 0.05;
  const ipv4 = 0.03;
  const storage = Math.max(0.01, (stagingBytes / (1024 * 1024 * 1024)) * 0.02);
  const egress = 0.04;
  const retries = (computeBase + startup + ipv4) * 0.1;
  const total = computeBase + startup + ipv4 + storage + egress + retries;

  const canSubmit = diagnosis.ok_to_submit(acks) && !isSubmitting;

  return (
    <div
      data-testid="plan-cost-sheet"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
    >
      <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-gray-200 bg-white shadow-2xl dark:border-gray-700 dark:bg-gray-900">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-800">
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
              Plan & Cost Confirmation
            </h2>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Review resource allocation, cost breakdown, and risk analysis
              before cloud dispatch.
            </p>
          </div>
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-200"
            aria-label="Close"
          >
            ✕
          </button>
        </header>

        {/* Content Body */}
        <div className="flex-1 space-y-6 overflow-y-auto px-6 py-4">
          {/* Job Overview Grid */}
          <div className="grid grid-cols-2 gap-4 rounded-lg bg-gray-50 p-4 text-sm dark:bg-gray-800/50">
            <div>
              <span className="font-semibold text-gray-500 dark:text-gray-400">Job ID:</span>{" "}
              <span className="font-mono text-gray-900 dark:text-gray-100">{spec.job_id}</span>
            </div>
            <div>
              <span className="font-semibold text-gray-500 dark:text-gray-400">Workload:</span>{" "}
              <span className="capitalize text-gray-900 dark:text-gray-100">{spec.kind}</span>
            </div>
            <div>
              <span className="font-semibold text-gray-500 dark:text-gray-400">Target:</span>{" "}
              <span className="font-medium text-gray-900 dark:text-gray-100">
                {spec.placement.provider.toUpperCase()} ({spec.placement.region})
              </span>
            </div>
            <div>
              <span className="font-semibold text-gray-500 dark:text-gray-400">Execution Mode:</span>{" "}
              <span className="text-gray-900 dark:text-gray-100">{spec.placement.mode}</span>
            </div>
            <div>
              <span className="font-semibold text-gray-500 dark:text-gray-400">Data Class:</span>{" "}
              <span className="capitalize text-gray-900 dark:text-gray-100">{spec.data_class}</span>
            </div>
            <div>
              <span className="font-semibold text-gray-500 dark:text-gray-400">Storage Method:</span>{" "}
              <span className="text-gray-900 dark:text-gray-100">{spec.storage}</span>
            </div>
            <div>
              <span className="font-semibold text-gray-500 dark:text-gray-400">Shards:</span>{" "}
              <span className="text-gray-900 dark:text-gray-100">{spec.shards.length}</span>
            </div>
            <div>
              <span className="font-semibold text-gray-500 dark:text-gray-400">Staging Size:</span>{" "}
              <span className="text-gray-900 dark:text-gray-100">{formatBytes(stagingBytes)}</span>
            </div>
          </div>

          {/* Cost Estimate Breakdown */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
              Estimated Total Job Cost Breakdown
            </h3>
            <div className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
              <div className="grid grid-cols-2 gap-y-2 text-xs text-gray-600 dark:text-gray-300">
                <div>Compute runtime:</div>
                <div className="text-right font-mono">{formatUsd(computeBase)}</div>
                <div>Node cold-start:</div>
                <div className="text-right font-mono">{formatUsd(startup)}</div>
                <div>Public IPv4 address:</div>
                <div className="text-right font-mono">{formatUsd(ipv4)}</div>
                <div>Staging bucket storage:</div>
                <div className="text-right font-mono">{formatUsd(storage)}</div>
                <div>Egress transfer:</div>
                <div className="text-right font-mono">{formatUsd(egress)}</div>
                <div>Retries contingency:</div>
                <div className="text-right font-mono">{formatUsd(retries)}</div>
                <div className="border-t border-gray-200 pt-2 font-bold text-gray-900 dark:border-gray-700 dark:text-gray-100">
                  Estimated Total:
                </div>
                <div className="border-t border-gray-200 pt-2 text-right font-mono font-bold text-emerald-600 dark:border-gray-700 dark:text-emerald-400">
                  {formatUsd(total)}
                </div>
              </div>
            </div>
          </section>

          {/* Risk Findings & Acknowledgments */}
          {diagnosis.findings.length > 0 && (
            <section className="space-y-3" data-testid="risk-findings-section">
              <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-200">
                Risk Engine Findings & Safeguards
              </h3>
              <div className="space-y-2">
                {diagnosis.findings.map((f) => (
                  <div
                    key={f.rule_id}
                    data-testid={`risk-finding-${f.rule_id}`}
                    className={`rounded-lg border p-3 text-xs ${getRiskBannerClass(f.severity)}`}
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-base font-bold">⚠</span>
                      <div className="flex-1">
                        <div className="font-semibold uppercase tracking-wider">{f.severity}: {f.rule_id}</div>
                        <p className="mt-0.5">{f.message}</p>
                        {f.requires_ack && (
                          <label className="mt-2 flex items-center gap-2 font-medium cursor-pointer">
                            <input
                              type="checkbox"
                              data-testid={`ack-checkbox-${f.rule_id}`}
                              checked={acks.has(f.rule_id)}
                              onChange={() => toggleAck(f.rule_id)}
                              className="rounded border-gray-400 text-indigo-600 focus:ring-indigo-500"
                            />
                            <span>I understand and acknowledge this risk before submission</span>
                          </label>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {diagnosis.blocking.length > 0 && (
            <div
              data-testid="blocking-banner"
              className="rounded-lg bg-red-100 p-3 text-xs font-semibold text-red-800 dark:bg-red-950/80 dark:text-red-200"
            >
              ⚠ Submission is blocked. You must resolve all blocking issues before dispatching this job.
            </div>
          )}
        </div>

        {/* Action Footer */}
        <footer className="flex items-center justify-end gap-3 border-t border-gray-200 bg-gray-50 px-6 py-4 dark:border-gray-800 dark:bg-gray-900/50">
          <button
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Cancel / Edit Spec
          </button>
          <button
            onClick={() => void onConfirmSubmit()}
            disabled={!canSubmit}
            data-testid="confirm-submit-button"
            className="flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? "Submitting Job..." : "Submit Cloud Job 🚀"}
          </button>
        </footer>
      </div>
    </div>
  );
}
