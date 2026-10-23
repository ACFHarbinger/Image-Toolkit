import React from "react";
import { JobSpec, WorkloadKind } from "./jobSpec";
import { getRiskInputClass, RiskDiagnosis } from "./risk";

export interface TaskSectionProps {
  spec: JobSpec;
  diagnosis: RiskDiagnosis;
  onKindChange: (kind: WorkloadKind) => void;
  onPresetChange: (preset: string) => void;
  onTitleChange: (title: string) => void;
  onShardsCountChange: (count: number) => void;
  renderFieldRisk: (fieldName: string) => React.ReactNode;
}

export function TaskSection({
  spec,
  diagnosis,
  onKindChange,
  onPresetChange,
  onTitleChange,
  onShardsCountChange,
  renderFieldRisk,
}: TaskSectionProps): React.ReactElement {
  return (
    <section className="space-y-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <div className="flex items-center justify-between border-b pb-2 dark:border-gray-800">
        <h3 className="text-sm font-bold uppercase tracking-wider text-gray-700 dark:text-gray-300">
          1. Task Specification
        </h3>
        <select
          data-testid="preset-selector"
          onChange={(e) => onPresetChange(e.target.value)}
          className="rounded border border-gray-300 bg-white px-2 py-1 text-xs text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
        >
          <option value="custom">Custom Configuration</option>
          <option value="convert">Convert Tab Selection</option>
          <option value="extract">Video Extractor Selection</option>
          <option value="comfy">ComfyUI Generation Batch</option>
        </select>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
          Workload Kind
        </label>
        <select
          data-testid="input-workload-kind"
          value={spec.kind}
          onChange={(e) => onKindChange(e.target.value as WorkloadKind)}
          className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm dark:border-gray-700 dark:bg-gray-800"
        >
          <option value="extract">Frame Extraction (Managed Batch)</option>
          <option value="comfy_batch">ComfyUI Batch Generation (Dedicated Instance)</option>
          <option value="index">Vector / CLIP Indexing (Managed Batch)</option>
          <option value="lora_train">LoRA / LyCORIS Training (Resumable Instance)</option>
        </select>
        {renderFieldRisk("job.kind")}
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
          Job Title
        </label>
        <input
          type="text"
          data-testid="input-job-title"
          value={spec.title ?? ""}
          placeholder="e.g. Batch extraction: episode 1"
          onChange={(e) => onTitleChange(e.target.value)}
          className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm dark:border-gray-700 dark:bg-gray-800"
        />
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
          Shards Manifest Count ({spec.shards.length} shards)
        </label>
        <input
          type="number"
          min={1}
          max={1000}
          data-testid="input-shards-count"
          value={spec.shards.length}
          onChange={(e) => onShardsCountChange(parseInt(e.target.value || "1", 10))}
          className={`mt-1 w-full rounded-md p-2 text-sm ${getRiskInputClass(
            diagnosis.severity_of("shards"),
          )}`}
        />
        {renderFieldRisk("shards")}
      </div>
    </section>
  );
}
