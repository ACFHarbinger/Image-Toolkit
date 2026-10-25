import React, { useMemo, useRef, useState } from "react";
import type { HostClient } from "../../hostclient";
import {
  createDefaultJobSpec,
  DataClass,
  DEFAULT_MODE,
  DEFAULT_RESOURCES,
  ExecutionMode,
  formatBytes,
  generateJobId,
  JobSpec,
  jobSpecFromComfy,
  jobSpecFromConvert,
  jobSpecFromExtract,
  StorageMethod,
  WorkloadKind,
} from "./jobSpec";
import { PlacementSection } from "./PlacementSection";
import { PlanCostSheet, type CostBreakdown } from "./PlanCostSheet";
import { previewDiagnosis } from "./previewRisk";
import type { RiskDiagnosis } from "./risk";
import { evaluateRisk, getRiskInputClass } from "./risk";
import { TaskSection } from "./TaskSection";

export interface ConvertOrigin {
  inputPaths: string[];
  outputFormat: string;
  deleteOriginal?: boolean;
}

export interface ExtractOrigin {
  mediaPath: string;
  startMs: number;
  endMs: number;
  fps: number;
  resolution: string;
}

export interface ComfyOrigin {
  workflow: Record<string, unknown>;
  prompts: string[];
}

/** Real tab selections. Absent entries leave that preset disabled. */
export interface RequestOrigins {
  convert?: ConvertOrigin | null;
  extract?: ExtractOrigin | null;
  comfy?: ComfyOrigin | null;
}

export interface RequestBuilderProps {
  client?: HostClient | null;
  origins?: RequestOrigins | null;
  onJobSubmitted?: (jobId: string, spec: JobSpec) => void;
}

function usableConvert(origin: ConvertOrigin | null | undefined): origin is ConvertOrigin {
  return !!origin && origin.inputPaths.some((path) => path.trim().length > 0) && origin.outputFormat.trim().length > 0;
}

function usableExtract(origin: ExtractOrigin | null | undefined): origin is ExtractOrigin {
  return !!origin && origin.mediaPath.trim().length > 0;
}

function usableComfy(origin: ComfyOrigin | null | undefined): origin is ComfyOrigin {
  return !!origin && origin.prompts.some((prompt) => prompt.trim().length > 0);
}

export function RequestBuilder({ client, origins, onJobSubmitted }: RequestBuilderProps): React.ReactElement {
  const [spec, setSpec] = useState<JobSpec>(() => createDefaultJobSpec("extract"));
  const [preset, setPreset] = useState("custom");
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastSubmittedId, setLastSubmittedId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [estimateKnown, setEstimateKnown] = useState(false);
  const [estimate, setEstimate] = useState<CostBreakdown | null>(null);
  const [submissionAvailable, setSubmissionAvailable] = useState(false);

  const [previewRisk, setPreviewRisk] = useState<RiskDiagnosis | null>(null);
  const previewGeneration = useRef(0);

  const hasWorkloadData = spec.shards.some((shard) =>
    Object.keys(shard.params ?? {}).length > 0 || (shard.inputs?.length ?? 0) > 0);

  const diagnosis = useMemo(() => evaluateRisk(spec), [spec]);

  const handleKindChange = (kind: WorkloadKind) => {
    setSpec((prev) => ({
      ...prev,
      kind,
      placement: { ...prev.placement, mode: DEFAULT_MODE[kind] },
      resources: { ...DEFAULT_RESOURCES[kind] },
      shards: [{ index: 0, params: {}, inputs: [] }],
    }));
  };

  const originReady = {
    convert: usableConvert(origins?.convert),
    extract: usableExtract(origins?.extract),
    comfy: usableComfy(origins?.comfy),
  };

  const handlePresetChange = (next: string) => {
    const provider = spec.placement.provider;
    const region = spec.placement.region;
    if (next === "convert") {
      if (!usableConvert(origins?.convert)) return;
      setPreset(next);
      setSpec(jobSpecFromConvert({ ...origins.convert, provider, region }));
      return;
    }
    if (next === "extract") {
      if (!usableExtract(origins?.extract)) return;
      setPreset(next);
      setSpec(jobSpecFromExtract({ ...origins.extract, provider, region }));
      return;
    }
    if (next === "comfy") {
      if (!usableComfy(origins?.comfy)) return;
      setPreset(next);
      setSpec(jobSpecFromComfy({ ...origins.comfy, provider, region }));
      return;
    }
    setPreset("custom");
    setSpec(createDefaultJobSpec("extract"));
  };

  const openSheet = () => {
    const generation = ++previewGeneration.current;
    setPreviewRisk(null);
    setIsSheetOpen(true);
    setEstimateKnown(false);
    setEstimate(null);
    setSubmissionAvailable(false);
    if (!client) {
      return;
    }
    void client
      .cloudJobsPreview({ spec: spec as unknown as Record<string, unknown> })
      .then((result) => {
        if (generation !== previewGeneration.current) return;
        setPreviewRisk(previewDiagnosis(result));
        setSubmissionAvailable(result.available);
        setEstimateKnown(result.estimate_known);
        setEstimate(result.estimate);
      })
      .catch(() => {
        if (generation !== previewGeneration.current) return;
        setSubmissionAvailable(false);
        setEstimateKnown(false);
        setEstimate(null);
      });
  };

  const handleSubmit = async (acknowledged: string[]) => {
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      if (!client || !submissionAvailable || !previewRisk?.ok_to_submit(new Set(acknowledged))) {
        setSubmitError("Cloud submission is unavailable");
        return;
      }
      const result = await client.cloudJobsSubmit({
        spec: spec as unknown as Record<string, unknown>,
        acknowledged,
      });
      if (!result.accepted) {
        setSubmitError(result.reason || "Cloud submission is unavailable");
        return;
      }
      setSpec((current) => ({ ...current, job_id: generateJobId() }));
      setLastSubmittedId(result.job_id);
      setIsSheetOpen(false);
      onJobSubmitted?.(result.job_id, spec);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderFieldRisk = (fieldName: string) => {
    const hits = diagnosis.for_field(fieldName);
    if (hits.length === 0) return null;
    return (
      <div className="mt-1 space-y-1">
        {hits.map((h) => (
          <p
            key={h.rule_id}
            data-testid={`field-risk-${fieldName}`}
            className={`flex items-center gap-1 text-xs font-semibold ${
              h.severity === "block"
                ? "text-red-600 dark:text-red-400"
                : h.severity === "warn"
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-blue-600 dark:text-blue-400"
            }`}
          >
            <span>⚠</span>
            <span>{h.message}</span>
          </p>
        ))}
      </div>
    );
  };

  return (
    <div data-testid="cloud-jobs-request-builder" className="space-y-6">
      <div className="flex items-center justify-between border-b pb-4 dark:border-gray-800">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">
            Cloud Job Request Builder
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Define task parameters, compute shapes, data isolation, and review risk safeguards.
          </p>
        </div>
      </div>

      {lastSubmittedId && (
        <div
          data-testid="submit-success-banner"
          className="flex items-center justify-between rounded-lg bg-emerald-100 p-4 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-200"
        >
          <div>
            <span className="font-bold">✓ Job Dispatched: </span>
            <span className="font-mono">{lastSubmittedId}</span>
          </div>
          <button onClick={() => setLastSubmittedId(null)} className="text-xs font-semibold underline">
            Dismiss
          </button>
        </div>
      )}

      {submitError && (
        <div
          data-testid="submit-error-banner"
          className="rounded-lg bg-red-100 p-4 text-xs font-semibold text-red-800 dark:bg-red-950/70 dark:text-red-200"
        >
          ⚠ Submission failed: {submitError}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <TaskSection
          spec={spec}
          diagnosis={diagnosis}
          preset={preset}
          origins={originReady}
          onKindChange={handleKindChange}
          onPresetChange={handlePresetChange}
          onTitleChange={(title) => setSpec({ ...spec, title })}
          shardsLocked={hasWorkloadData}
          onShardsCountChange={(count) => {
            if (hasWorkloadData || !Number.isFinite(count)) return;
            const cnt = Math.min(1000, Math.max(1, Math.floor(count)));
            setSpec({
              ...spec,
              shards: Array.from({ length: cnt }, (_, i) => ({ index: i, params: {}, inputs: [] })),
            });
          }}
          renderFieldRisk={renderFieldRisk}
        />

        <PlacementSection
          spec={spec}
          diagnosis={diagnosis}
          onProviderChange={(provider) =>
            setSpec({ ...spec, placement: { ...spec.placement, provider } })
          }
          onRegionChange={(region) => setSpec({ ...spec, placement: { ...spec.placement, region } })}
          onModeChange={(mode: ExecutionMode) =>
            setSpec({ ...spec, placement: { ...spec.placement, mode } })
          }
          onGpuClassChange={(gpu_class) =>
            setSpec({
              ...spec,
              resources: {
                ...spec.resources,
                gpu_class: gpu_class || null,
                gpu_count: gpu_class ? Math.max(1, spec.resources.gpu_count) : 0,
              },
            })
          }
          onGpuCountChange={(gpu_count) =>
            setSpec({ ...spec, resources: { ...spec.resources, gpu_count } })
          }
          renderFieldRisk={renderFieldRisk}
        />

        {/* Section 3: Data Security & Storage */}
        <section className="space-y-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="border-b pb-2 text-sm font-bold uppercase tracking-wider text-gray-700 dark:border-gray-800 dark:text-gray-300">
            3. Data Isolation & Storage
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                Data Classification
              </label>
              <select
                data-testid="input-data-class"
                value={spec.data_class}
                onChange={(e) => setSpec({ ...spec, data_class: e.target.value as DataClass })}
                className={`mt-1 w-full rounded-md p-2 text-sm ${getRiskInputClass(
                  diagnosis.severity_of("data_class"),
                )}`}
              >
                <option value="public">Public (Open Training Data)</option>
                <option value="private">Private (Default Isolation)</option>
                <option value="sensitive">Sensitive (Restricted Allowlist)</option>
              </select>
              {renderFieldRisk("data_class")}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                Storage Transfer Method
              </label>
              <select
                data-testid="input-storage-method"
                value={spec.storage}
                onChange={(e) => setSpec({ ...spec, storage: e.target.value as StorageMethod })}
                className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm dark:border-gray-700 dark:bg-gray-800"
              >
                <option value="bucket">Object Storage Bucket (S3/GCS)</option>
                <option value="provider_native">Provider Native Network Volume</option>
                <option value="cloud_sync">Cloud Sync Transport</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
              Digest-Pinned Worker Container Image
            </label>
            <input
              type="text"
              data-testid="input-worker-image"
              value={spec.image ?? ""}
              onChange={(e) => setSpec({ ...spec, image: e.target.value })}
              className={`mt-1 w-full rounded-md p-2 font-mono text-xs ${getRiskInputClass(
                diagnosis.severity_of("image"),
              )}`}
            />
            {renderFieldRisk("image")}
          </div>
        </section>

        {/* Section 4: Safeguards & Spending Limits */}
        <section className="space-y-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <h3 className="border-b pb-2 text-sm font-bold uppercase tracking-wider text-gray-700 dark:border-gray-800 dark:text-gray-300">
            4. Safeguards & Spending Limits
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                Max Spend Hard Cap (USD)
              </label>
              <input
                type="number"
                step="0.5"
                data-testid="input-max-spend"
                value={spec.limits.max_spend_usd ?? ""}
                onChange={(e) =>
                  setSpec({
                    ...spec,
                    limits: { ...spec.limits, max_spend_usd: parseFloat(e.target.value) || null },
                  })
                }
                className={`mt-1 w-full rounded-md p-2 text-sm ${getRiskInputClass(
                  diagnosis.severity_of("limits.max_spend_usd"),
                )}`}
              />
              {renderFieldRisk("limits.max_spend_usd")}
            </div>

            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
                Max Runtime (seconds)
              </label>
              <input
                type="number"
                step="60"
                data-testid="input-max-runtime"
                value={spec.limits.max_runtime_s ?? ""}
                onChange={(e) =>
                  setSpec({
                    ...spec,
                    limits: { ...spec.limits, max_runtime_s: parseInt(e.target.value, 10) || null },
                  })
                }
                className={`mt-1 w-full rounded-md p-2 text-sm ${getRiskInputClass(
                  diagnosis.severity_of("limits.max_runtime_s"),
                )}`}
              />
              {renderFieldRisk("limits.max_runtime_s")}
            </div>
          </div>

          <div className="pt-2">
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                data-testid="input-spot-allowed"
                checked={spec.limits.spot_allowed}
                onChange={(e) =>
                  setSpec({
                    ...spec,
                    limits: { ...spec.limits, spot_allowed: e.target.checked },
                  })
                }
                className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                Allow Spot / Preemptible Instances (lower cost, subject to eviction)
              </span>
            </label>
            {renderFieldRisk("limits.spot_allowed")}
          </div>
        </section>
      </div>

      {/* Review & Plan Action Footer */}
      <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-900/50">
        <div className="text-xs text-gray-500 dark:text-gray-400">
          <span>{spec.shards.length} shards configured • </span>
          <span>
            Staging size:{" "}
            {formatBytes(
              Object.values(spec.inputs ?? {}).reduce((acc, b) => acc + (b.size_bytes || 0), 0),
            )}
          </span>
        </div>
        <div className="flex gap-3">
          <button
            type="button"
            data-testid="reset-form-button"
            onClick={() => setSpec(createDefaultJobSpec("extract"))}
            className="rounded-lg border border-gray-300 px-4 py-2 text-xs font-semibold text-gray-700 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            Reset Form
          </button>
          <button
            type="button"
            data-testid="review-plan-button"
            onClick={openSheet}
            className="rounded-lg bg-indigo-600 px-6 py-2 text-xs font-bold text-white shadow hover:bg-indigo-700"
          >
            Review Plan & Cost Sheet 📋
          </button>
        </div>
      </div>

      {isSheetOpen && (
        <PlanCostSheet
          spec={spec}
          diagnosis={previewRisk ?? diagnosis}
          onConfirmSubmit={handleSubmit}
          onClose={() => { previewGeneration.current += 1; setIsSheetOpen(false); }}
          isSubmitting={isSubmitting}
          estimateKnown={estimateKnown}
          estimate={estimate}
          submissionAvailable={submissionAvailable}
        />
      )}
    </div>
  );
}
