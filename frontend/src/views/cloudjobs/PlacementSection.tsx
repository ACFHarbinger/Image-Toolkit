import React from "react";
import { ExecutionMode, JobSpec } from "./jobSpec";
import { getRiskInputClass, RiskDiagnosis } from "./risk";

export interface PlacementSectionProps {
  spec: JobSpec;
  diagnosis: RiskDiagnosis;
  onProviderChange: (provider: string) => void;
  onRegionChange: (region: string) => void;
  onModeChange: (mode: ExecutionMode) => void;
  onGpuClassChange: (gpuClass: string) => void;
  onGpuCountChange: (count: number) => void;
  renderFieldRisk: (fieldName: string) => React.ReactNode;
}

export function PlacementSection({
  spec,
  diagnosis,
  onProviderChange,
  onRegionChange,
  onModeChange,
  onGpuClassChange,
  onGpuCountChange,
  renderFieldRisk,
}: PlacementSectionProps): React.ReactElement {
  return (
    <section className="space-y-4 rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-gray-900">
      <h3 className="border-b pb-2 text-sm font-bold uppercase tracking-wider text-gray-700 dark:border-gray-800 dark:text-gray-300">
        2. Compute Environment & Placement
      </h3>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
            Target Provider
          </label>
          <select
            data-testid="input-provider"
            value={spec.placement.provider}
            onChange={(e) => onProviderChange(e.target.value)}
            className={`mt-1 w-full rounded-md p-2 text-sm ${getRiskInputClass(
              diagnosis.severity_of("placement.provider"),
            )}`}
          >
            <option value="runpod">RunPod GPU Cloud</option>
            <option value="gcp">Google Cloud Platform (GCP)</option>
            <option value="aws">Amazon Web Services (AWS)</option>
            <option value="azure">Microsoft Azure</option>
            <option value="hyperstack">Hyperstack Bare-Metal</option>
          </select>
          {renderFieldRisk("placement.provider")}
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
            Region
          </label>
          <select
            data-testid="input-region"
            value={spec.placement.region}
            onChange={(e) => onRegionChange(e.target.value)}
            className={`mt-1 w-full rounded-md p-2 text-sm ${getRiskInputClass(
              diagnosis.severity_of("placement.region"),
            )}`}
          >
            <option value="us-central1">us-central1 (Iowa)</option>
            <option value="us-east-1">us-east-1 (Virginia)</option>
            <option value="eu-west-1">eu-west-1 (Ireland)</option>
            <option value="asia-east1">asia-east1 (Taiwan)</option>
            <option value="norway-1">norway-1 (Hyperstack)</option>
          </select>
          {renderFieldRisk("placement.region")}
        </div>
      </div>

      <div>
        <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
          Execution Mode
        </label>
        <select
          data-testid="input-execution-mode"
          value={spec.placement.mode}
          disabled={diagnosis.disabled_fields.has("placement.mode")}
          onChange={(e) => onModeChange(e.target.value as ExecutionMode)}
          className={`mt-1 w-full rounded-md p-2 text-sm ${
            diagnosis.disabled_fields.has("placement.mode")
              ? "cursor-not-allowed opacity-50"
              : ""
          } ${getRiskInputClass(diagnosis.severity_of("placement.mode"))}`}
        >
          <option value="managed_batch">Managed Batch (Serverless Worker Pool)</option>
          <option value="instance">Dedicated Remote Instance (VM/Pod)</option>
        </select>
        {renderFieldRisk("placement.mode")}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
            GPU Class
          </label>
          <input
            type="text"
            data-testid="input-gpu-class"
            value={spec.resources.gpu_class ?? ""}
            placeholder="e.g. NVIDIA-RTX-4090"
            onChange={(e) => onGpuClassChange(e.target.value)}
            className={`mt-1 w-full rounded-md p-2 text-sm ${getRiskInputClass(
              diagnosis.severity_of("resources.gpu_class"),
            )}`}
          />
          {renderFieldRisk("resources.gpu_class")}
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 dark:text-gray-300">
            GPU Count
          </label>
          <input
            type="number"
            min={0}
            max={8}
            data-testid="input-gpu-count"
            value={spec.resources.gpu_count}
            onChange={(e) => onGpuCountChange(parseInt(e.target.value || "0", 10))}
            className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm dark:border-gray-700 dark:bg-gray-800"
          />
        </div>
      </div>
    </section>
  );
}
