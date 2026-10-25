/**
 * Provider-neutral job specification models (#826, #850).
 *
 * Origin tabs and the Request Builder construct the identical JobSpec,
 * preventing drift between submission surfaces.
 */

export type WorkloadKind = "extract" | "comfy_batch" | "index" | "lora_train";
export type ExecutionMode = "instance" | "managed_batch";
export type StorageMethod = "bucket" | "provider_native" | "cloud_sync";
export type DataClass = "public" | "private" | "sensitive";

export interface Placement {
  provider: string;
  region: string;
  mode: ExecutionMode;
  instance_type?: string;
}

export interface Resources {
  vcpu: number;
  memory_gb: number;
  gpu_class?: string | null;
  gpu_count: number;
  vram_gb_min: number;
  disk_gb: number;
}

export interface Limits {
  max_runtime_s?: number | null;
  max_spend_usd?: number | null;
  spot_allowed: boolean;
  deadline_ts?: number | null;
}

export interface InputBlob {
  sha256: string;
  size_bytes: number;
  name: string;
  local_path?: string | null;
}

export interface ShardSpec {
  index: number;
  params?: Record<string, unknown>;
  inputs?: string[];
}

export interface JobSpec {
  job_id: string;
  kind: WorkloadKind;
  placement: Placement;
  shards: ShardSpec[];
  resources: Resources;
  limits: Limits;
  data_class: DataClass;
  storage: StorageMethod;
  image?: string;
  inputs?: Record<string, InputBlob>;
  params?: Record<string, unknown>;
  title?: string;
  scheduled_at?: number | null;
}

export const RESUMABLE_KINDS: ReadonlySet<WorkloadKind> = new Set(["lora_train"]);

export const DEFAULT_MODE: Record<WorkloadKind, ExecutionMode> = {
  extract: "managed_batch",
  index: "managed_batch",
  comfy_batch: "instance",
  lora_train: "instance",
};

export const DEFAULT_RESOURCES: Record<WorkloadKind, Resources> = {
  extract: { vcpu: 2, memory_gb: 4, gpu_class: null, gpu_count: 0, vram_gb_min: 0, disk_gb: 20 },
  index: { vcpu: 4, memory_gb: 8, gpu_class: null, gpu_count: 0, vram_gb_min: 0, disk_gb: 40 },
  comfy_batch: { vcpu: 8, memory_gb: 16, gpu_class: "NVIDIA-RTX-4090", gpu_count: 1, vram_gb_min: 24, disk_gb: 50 },
  lora_train: { vcpu: 8, memory_gb: 32, gpu_class: "NVIDIA-A100-SXM4", gpu_count: 1, vram_gb_min: 40, disk_gb: 100 },
};

export function generateJobId(): string {
  const hex = Math.random().toString(16).slice(2, 14).padEnd(12, "0");
  return `cj-${hex}`;
}

export function createDefaultJobSpec(kind: WorkloadKind = "extract"): JobSpec {
  return {
    job_id: generateJobId(),
    kind,
    placement: {
      provider: "runpod",
      region: "us-central1",
      mode: DEFAULT_MODE[kind],
    },
    shards: [{ index: 0, params: {}, inputs: [] }],
    resources: { ...DEFAULT_RESOURCES[kind] },
    limits: {
      max_runtime_s: 3600,
      max_spend_usd: 10.0,
      spot_allowed: false,
      deadline_ts: null,
    },
    data_class: "private",
    storage: "bucket",
    image: "ghcr.io/image-toolkit/worker@sha256:7b28c894e63412356c9a7516fbc82b3a6ef4e11234567890abcdef1234567890",
    inputs: {},
    params: {},
    title: "",
    scheduled_at: null,
  };
}

export function validateJobSpec(spec: JobSpec): string[] {
  const errors: string[] = [];
  if (!spec.shards || spec.shards.length === 0) {
    errors.push("A job needs at least one shard.");
  }
  if (spec.shards && spec.shards.length > 10_000) {
    errors.push("Cannot exceed 10,000 shards.");
  }
  if (spec.shards) {
    const indices = spec.shards.map((s) => s.index).sort((a, b) => a - b);
    for (let i = 0; i < indices.length; i++) {
      if (indices[i] !== i) {
        errors.push(`Shard indices must be continuous 0..${indices.length - 1}`);
        break;
      }
    }
  }
  if (spec.kind === "lora_train" && spec.shards && spec.shards.length !== 1) {
    errors.push("LoRA training is a single-shard job.");
  }
  if (spec.image && !spec.image.includes("@sha256:")) {
    errors.push(`Worker image must be digest-pinned with @sha256: (${spec.image})`);
  }
  if (spec.limits.max_runtime_s !== undefined && spec.limits.max_runtime_s !== null && spec.limits.max_runtime_s <= 0) {
    errors.push("max_runtime_s must be positive.");
  }
  if (spec.limits.max_spend_usd !== undefined && spec.limits.max_spend_usd !== null && spec.limits.max_spend_usd <= 0) {
    errors.push("max_spend_usd must be positive.");
  }
  return errors;
}

export function jobSpecFromConvert(params: {
  inputPaths: string[];
  outputFormat: string;
  provider?: string;
  region?: string;
  deleteOriginal?: boolean;
}): JobSpec {
  const spec = createDefaultJobSpec("extract");
  spec.title = `Batch Convert to .${params.outputFormat} (${params.inputPaths.length} items)`;
  spec.placement.provider = params.provider ?? "runpod";
  spec.placement.region = params.region ?? "us-central1";
  spec.params = {
    action: "convert",
    output_format: params.outputFormat,
    delete_original: !!params.deleteOriginal,
    files_count: params.inputPaths.length,
  };
  spec.shards = params.inputPaths.map((path, idx) => ({
    index: idx,
    params: { file_path: path, output_format: params.outputFormat },
    inputs: [],
  }));
  return spec;
}

export function jobSpecFromExtract(params: {
  mediaPath: string;
  startMs: number;
  endMs: number;
  fps: number;
  resolution: string;
  provider?: string;
  region?: string;
}): JobSpec {
  const spec = createDefaultJobSpec("extract");
  spec.title = `Extract Frames: ${params.mediaPath.split("/").pop() ?? "Media"}`;
  spec.placement.provider = params.provider ?? "runpod";
  spec.placement.region = params.region ?? "us-central1";
  spec.params = {
    media_path: params.mediaPath,
    start_ms: params.startMs,
    end_ms: params.endMs,
    fps: params.fps,
    resolution: params.resolution,
  };
  const durationMs = Math.max(0, params.endMs - params.startMs);
  const estimatedFrames = Math.max(1, Math.round((durationMs / 1000) * params.fps));
  const shardCount = Math.max(1, Math.min(20, Math.ceil(estimatedFrames / 100)));
  spec.shards = Array.from({ length: shardCount }, (_, i) => ({
    index: i,
    params: { shard_part: i + 1, total_shards: shardCount },
    inputs: [],
  }));
  return spec;
}

export function jobSpecFromComfy(params: {
  workflow: Record<string, unknown>;
  prompts: string[];
  provider?: string;
  region?: string;
}): JobSpec {
  const spec = createDefaultJobSpec("comfy_batch");
  spec.title = `ComfyUI Batch (${params.prompts.length} prompts)`;
  spec.placement.provider = params.provider ?? "runpod";
  spec.placement.region = params.region ?? "us-central1";
  spec.params = {
    workflow: params.workflow,
    prompt_count: params.prompts.length,
  };
  spec.shards = params.prompts.map((prompt, idx) => ({
    index: idx,
    params: { prompt, seed: 1000 + idx },
    inputs: [],
  }));
  return spec;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(2)} GB`;
}

export function formatUsd(amount: number): string {
  return `$${amount.toFixed(2)}`;
}
