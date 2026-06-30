/** Benchmark analytics computation layer.
 *
 *  All pure-function analytics derived from the JSON schemas produced by
 *  `backend/benchmark/utils.py` (general) and `bench_anime_stitch.py` (ASP).
 *  Uses the math backbone (stats.ts, colormap.ts) for computation; the
 *  dashboard component calls these functions and renders SVG from the results.
 */

import { mean, min, max } from './stats';
import { applyColormapHex } from './colormap';

// ── Type mirrors of the Tauri Rust types (kept in sync) ──────────────────────

export interface BenchmarkTime {
  avg_sec: number;
  min_sec: number;
  max_sec: number;
  total_sec: number;
}

export interface BenchmarkMemory {
  avg_peak_mb: number;
  max_peak_mb: number;
  avg_delta_mb: number;
  max_leaked_mb: number;
}

export interface GeneralBenchmark {
  name: string;
  iterations: number;
  time: BenchmarkTime;
  memory: BenchmarkMemory;
}

export interface AspMetrics {
  sharpness: number;
  coverage: number;
  seam_gradient: number;
  color_entropy: number;
  ghosting_score: number;
  ghosting_siqe?: number;
  seam_coherence: number;
  seam_visibility?: number;
  strip_banding_score?: number;
  ghost_seam_max?: number;
  ghost_seam_scores?: number[];
  seam_color_min?: number;
  seam_color_scores?: number[];
  seam_ncc_min?: number;
  seam_ncc_scores?: number[];
  composite_quality?: number;
  width?: number;
  height?: number;
  rlhf_score?: number;
  rlhf_flagged?: boolean;
  rlhf_uncertainty?: number;
  rlhf_needs_review?: boolean;
}

export interface AspAffineEntry { frame: number; tx: number; ty: number; a: number; b: number; }
export interface AspAlignment {
  affines: AspAffineEntry[];
  dy_steps: number[];
  dx_steps: number[];
  dy_cv: number;
  dx_cv: number;
}
export interface AspPhotometric {
  ref_lum?: number;
  bg_lums: (number | null)[];
  applied_gains: number[];
  frames_corrected: number;
  gain_range: number[];
}
export interface AspAffineHealth {
  valid: boolean;
  ratio: number;
  min_gap_px: number;
  max_rotation: number;
  max_scale_dev: number;
  reason: string;
}
export interface AspFrameSelection {
  original_count: number;
  smart_select_count: number;
  spatial_dedup_count: number;
  final_count: number;
  frames_dropped_smart: number;
  frames_dropped_dedup: number;
  selection_mode: string;
}

export interface AspTiming {
  simple_stitch_sec?: number;
  birefnet_sec?: number;
  matching_sec?: number;
  bundle_adjust_sec?: number;
  ecc_sec?: number;
  render_sec?: number;
  composite_sec?: number;
  visualisations_sec?: number;
  total_sec: number;
}

export interface AspDataset {
  name: string;
  used_fallback: boolean;
  time: AspTiming;
  frame_count?: number;
  canvas_width?: number;
  canvas_height?: number;
  metrics_asp?: AspMetrics;
  metrics_simple?: AspMetrics;
  comparison?: Record<string, unknown>;
  ground_truth?: { ssim_vs_gt?: number; aligned_ssim_vs_gt?: number; psnr_vs_gt?: number; verdict?: string };
  matching?: Record<string, unknown>;
  fallback_reason?: string;
  alignment?: AspAlignment;
  photometric?: AspPhotometric;
  affine_health?: AspAffineHealth;
  frame_selection?: AspFrameSelection;
  pipeline_config?: Record<string, unknown>;
}

export interface AspSummary {
  total_datasets: number;
  datasets_passed: number;
  datasets_fallback: number;
  total_time_sec: number;
  avg_time_per_dataset_sec: number;
  avg_sharpness_asp?: number;
  avg_sharpness_simple?: number;
  avg_ghosting_asp?: number;
  avg_coverage_asp?: number;
  verdict_counts?: Record<string, number>;
}

export interface GeneralSummary {
  total_execution_time_sec: number;
  max_peak_memory_mb: number;
  benchmarks_passed: number;
}

export interface SystemInfo {
  timestamp: string;
  platform: string;
  python?: string;
  cpu: string;
  cpu_threads?: number;
  ram_gb?: number;
  gpu?: string;
  cuda_version?: string;
  vram_gb?: number;
}

export type BenchmarkReport =
  | { kind: 'Asp'; file_name: string; system: SystemInfo; summary: AspSummary; datasets: AspDataset[] }
  | { kind: 'General'; file_name: string; suite_name: string; system: SystemInfo; summary: GeneralSummary; benchmarks: GeneralBenchmark[] };

// ── General benchmark analytics ───────────────────────────────────────────────

export interface EfficiencyEntry {
  name: string;
  score: number;        // 0–100, lower = more efficient
  avg_time: number;
  avg_mem: number;
  throughput: number;   // ops/sec
  color: string;        // hex CSS color from coolwarm colormap
}

/** Compute composite efficiency score (lower = better) and throughput for each benchmark. */
export function computeEfficiency(benchmarks: GeneralBenchmark[]): EfficiencyEntry[] {
  if (benchmarks.length === 0) return [];

  const times = benchmarks.map(b => b.time.avg_sec);
  const mems = benchmarks.map(b => b.memory.avg_peak_mb);
  const maxTime = max(times) || 1;
  const maxMem = max(mems) || 1;

  const scores = benchmarks.map(b =>
    ((b.time.avg_sec / maxTime) + (b.memory.avg_peak_mb / maxMem)) / 2 * 100
  );

  const colors = applyColormapHex(scores, 'coolwarm');

  return benchmarks.map((b, i) => ({
    name: b.name,
    score: Math.round(scores[i] * 10) / 10,
    avg_time: b.time.avg_sec,
    avg_mem: b.memory.avg_peak_mb,
    throughput: b.time.total_sec > 0 ? b.iterations / b.time.total_sec : 0,
    color: colors[i],
  })).sort((a, b) => a.score - b.score);
}

/** Memory-vs-time scatter data with efficiency-sized bubbles. */
export interface ScatterPoint {
  name: string;
  x: number;        // avg_sec (time)
  y: number;        // avg_peak_mb (memory)
  r: number;        // bubble radius 6–24
  color: string;
  efficiency: number;
  iterations: number;
}

export function computeMemoryVsTimeScatter(benchmarks: GeneralBenchmark[]): ScatterPoint[] {
  const entries = computeEfficiency(benchmarks);
  const entryMap = new Map(entries.map(e => [e.name, e]));
  const minR = 6, maxR = 24;
  const scores = entries.map(e => e.score);
  const minScore = min(scores) || 0;
  const maxScore = max(scores) || 100;
  const range = maxScore - minScore || 1;

  return benchmarks.map(b => {
    const e = entryMap.get(b.name)!;
    const norm = (e.score - minScore) / range;
    return {
      name: b.name,
      x: b.time.avg_sec,
      y: b.memory.avg_peak_mb,
      r: minR + norm * (maxR - minR),
      color: e.color,
      efficiency: e.score,
      iterations: b.iterations,
    };
  });
}

/** Memory breakdown stacked bar data: baseline + delta + leaked. */
export interface MemoryBreakdownEntry {
  name: string;
  baseline: number;
  delta: number;
  leaked: number;
}

export function computeMemoryBreakdown(benchmarks: GeneralBenchmark[]): MemoryBreakdownEntry[] {
  return benchmarks.map(b => ({
    name: b.name,
    baseline: Math.max(0, b.memory.avg_peak_mb - b.memory.avg_delta_mb),
    delta: Math.max(0, b.memory.avg_delta_mb),
    leaked: Math.max(0, b.memory.max_leaked_mb),
  }));
}

/** Time variance (%) = (max - min) / avg. */
export function timeVariancePct(b: GeneralBenchmark): number {
  if (b.time.avg_sec === 0) return 0;
  return ((b.time.max_sec - b.time.min_sec) / b.time.avg_sec) * 100;
}

/** Detect regressions vs a baseline list (by name match). */
export interface RegressionResult {
  name: string;
  time_delta_pct: number;
  mem_delta_pct: number;
  status: 'improvement' | 'ok' | 'time_regression' | 'mem_regression';
}

export function detectRegressions(
  current: GeneralBenchmark[],
  baseline: GeneralBenchmark[],
  timeThr = 0.20,
  memThr = 0.15,
): RegressionResult[] {
  const baseMap = new Map(baseline.map(b => [b.name, b]));
  return current.flatMap(b => {
    const base = baseMap.get(b.name);
    if (!base) return [];
    const timeDelta = (b.time.avg_sec - base.time.avg_sec) / (base.time.avg_sec || 1);
    const memDelta = (b.memory.avg_peak_mb - base.memory.avg_peak_mb) / (base.memory.avg_peak_mb || 1);
    let status: RegressionResult['status'] = 'ok';
    if (timeDelta > timeThr) status = 'time_regression';
    else if (memDelta > memThr) status = 'mem_regression';
    else if (timeDelta < -0.10 || memDelta < -0.10) status = 'improvement';
    return [{ name: b.name, time_delta_pct: timeDelta * 100, mem_delta_pct: memDelta * 100, status }];
  });
}

// ── ASP benchmark analytics ───────────────────────────────────────────────────

/** ASP pipeline time breakdown as percentage of total. */
export interface TimingBreakdown {
  stage: string;
  label: string;
  sec: number;
  pct: number;
  color: string;
}

const TIMING_STAGES: Array<{ key: keyof AspTiming; label: string }> = [
  { key: 'birefnet_sec', label: 'BiRefNet masking' },
  { key: 'matching_sec', label: 'Feature matching' },
  { key: 'bundle_adjust_sec', label: 'Bundle adjust' },
  { key: 'ecc_sec', label: 'ECC refinement' },
  { key: 'render_sec', label: 'Median render' },
  { key: 'composite_sec', label: 'Compositing' },
  { key: 'simple_stitch_sec', label: 'Simple stitch (ref)' },
  { key: 'visualisations_sec', label: 'Visualisations' },
];

const STAGE_PALETTE = ['#6366f1','#8b5cf6','#a78bfa','#c4b5fd','#22c55e','#16a34a','#f59e0b','#94a3b8'];

export function computeTimingBreakdown(timing: AspTiming): TimingBreakdown[] {
  const total = timing.total_sec || 1;
  return TIMING_STAGES
    .map((s, i) => {
      const sec = (timing[s.key] as number | undefined) ?? 0;
      return { stage: s.key, label: s.label, sec, pct: (sec / total) * 100, color: STAGE_PALETTE[i] };
    })
    .filter(s => s.sec > 0);
}

/** Aggregate CV metric comparison: ASP vs Simple stitch per dataset. */
export interface MetricComparison {
  dataset: string;
  metric: string;
  asp: number;
  simple: number;
  delta: number;       // asp - simple (positive = ASP better if higher-is-better)
  higherIsBetter: boolean;
  winner: 'asp' | 'simple' | 'tie';
}

const CV_METRICS: Array<{ key: keyof AspMetrics; label: string; higherIsBetter: boolean }> = [
  { key: 'sharpness', label: 'Sharpness', higherIsBetter: true },
  { key: 'coverage', label: 'Coverage', higherIsBetter: true },
  { key: 'color_entropy', label: 'Color Entropy', higherIsBetter: true },
  { key: 'ghosting_score', label: 'Ghosting (proxy)', higherIsBetter: false },
  { key: 'ghosting_siqe', label: 'Ghosting (SIQE)', higherIsBetter: false },
  { key: 'seam_coherence', label: 'Seam Coherence', higherIsBetter: false },
  { key: 'seam_visibility', label: 'Seam Visibility', higherIsBetter: false },
  { key: 'composite_quality', label: 'Composite Quality', higherIsBetter: true },
];

export function computeMetricComparisons(datasets: AspDataset[]): MetricComparison[] {
  const results: MetricComparison[] = [];
  for (const ds of datasets) {
    if (!ds.metrics_asp || !ds.metrics_simple) continue;
    for (const m of CV_METRICS) {
      const asp = ds.metrics_asp[m.key] as number | undefined;
      const simple = ds.metrics_simple[m.key] as number | undefined;
      if (asp == null || simple == null) continue;
      const delta = asp - simple;
      const aspWins = m.higherIsBetter ? delta > 0.02 : delta < -0.02;
      const simpleWins = m.higherIsBetter ? delta < -0.02 : delta > 0.02;
      results.push({
        dataset: ds.name,
        metric: m.label,
        asp,
        simple,
        delta,
        higherIsBetter: m.higherIsBetter,
        winner: aspWins ? 'asp' : simpleWins ? 'simple' : 'tie',
      });
    }
  }
  return results;
}

/** Seam quality heatmap: per-dataset seam metric scores in [0,1] space. */
export interface SeamQualityRow {
  dataset: string;
  composite_quality: number;
  seam_ncc_min: number;
  seam_color_min: number;
  ghosting_siqe_norm: number;  // 1 - clamp(v/100,0,1) → higher=better
  seam_visibility_norm: number; // 1 - clamp(v/50,0,1) → higher=better
  rlhf_score: number;          // already [0,1], or 0.5 if unavailable
  used_fallback: boolean;
}

export function computeSeamQualityHeatmap(datasets: AspDataset[]): SeamQualityRow[] {
  return datasets.map(ds => {
    const m = ds.metrics_asp;
    return {
      dataset: ds.name,
      composite_quality: m?.composite_quality ?? 0.5,
      seam_ncc_min: m?.seam_ncc_min != null ? (m.seam_ncc_min + 1) / 2 : 0.5,
      seam_color_min: m?.seam_color_min ?? 0.5,
      ghosting_siqe_norm: m?.ghosting_siqe != null ? Math.max(0, 1 - m.ghosting_siqe / 100) : 0.5,
      seam_visibility_norm: m?.seam_visibility != null ? Math.max(0, 1 - m.seam_visibility / 50) : 0.5,
      rlhf_score: m?.rlhf_score ?? 0.5,
      used_fallback: ds.used_fallback,
    };
  });
}

/** Verdict counts for ASP vs Simple stitch comparison. */
export function verdictSummary(datasets: AspDataset[]): { asp_better: number; simple_better: number; comparable: number; no_data: number } {
  const counts = { asp_better: 0, simple_better: 0, comparable: 0, no_data: 0 };
  for (const ds of datasets) {
    const v = (ds.comparison as any)?.verdict ?? (ds.ground_truth?.verdict);
    if (v === 'asp_better') counts.asp_better++;
    else if (v === 'simple_better') counts.simple_better++;
    else if (v === 'comparable') counts.comparable++;
    else counts.no_data++;
  }
  return counts;
}

/** Trend data: per-report timestamp + a selected scalar metric for one benchmark/dataset. */
export interface TrendPoint {
  timestamp: string;
  value: number;
  file_name: string;
}

export function extractGeneralTrend(
  reports: BenchmarkReport[],
  suiteName: string,
  benchName: string,
  field: 'avg_sec' | 'avg_peak_mb',
): TrendPoint[] {
  const points: TrendPoint[] = [];
  for (const r of reports) {
    if (r.kind !== 'General' || r.suite_name !== suiteName) continue;
    const bench = r.benchmarks.find(b => b.name === benchName);
    if (!bench) continue;
    const value = field === 'avg_sec' ? bench.time.avg_sec : bench.memory.avg_peak_mb;
    points.push({ timestamp: r.system.timestamp, value, file_name: r.file_name });
  }
  return points.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

export function extractAspTrend(
  reports: BenchmarkReport[],
  datasetName: string,
  field: keyof AspTiming | 'sharpness' | 'composite_quality',
): TrendPoint[] {
  const points: TrendPoint[] = [];
  for (const r of reports) {
    if (r.kind !== 'Asp') continue;
    const ds = r.datasets.find(d => d.name === datasetName);
    if (!ds) continue;
    let value: number | undefined;
    if (field in ds.time) {
      value = ds.time[field as keyof AspTiming] as number | undefined;
    } else if (field === 'sharpness') {
      value = ds.metrics_asp?.sharpness;
    } else if (field === 'composite_quality') {
      value = ds.metrics_asp?.composite_quality;
    }
    if (value == null) continue;
    points.push({ timestamp: r.system.timestamp, value, file_name: r.file_name });
  }
  return points.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

/** Compute summary statistics across all benchmarks in a general suite. */
export interface SuiteStats {
  total_time: number;
  avg_time: number;
  peak_mem: number;
  total_leaked: number;
  fastest: GeneralBenchmark;
  slowest: GeneralBenchmark;
  most_mem_efficient: GeneralBenchmark;
  most_mem_intensive: GeneralBenchmark;
  leaky: GeneralBenchmark[];
}

export function computeSuiteStats(benchmarks: GeneralBenchmark[]): SuiteStats | null {
  if (benchmarks.length === 0) return null;
  const sorted_t = [...benchmarks].sort((a, b) => a.time.avg_sec - b.time.avg_sec);
  const sorted_m = [...benchmarks].sort((a, b) => a.memory.avg_peak_mb - b.memory.avg_peak_mb);
  return {
    total_time: benchmarks.reduce((s, b) => s + b.time.total_sec, 0),
    avg_time: mean(benchmarks.map(b => b.time.avg_sec)),
    peak_mem: max(benchmarks.map(b => b.memory.max_peak_mb)),
    total_leaked: benchmarks.reduce((s, b) => s + b.memory.max_leaked_mb, 0),
    fastest: sorted_t[0],
    slowest: sorted_t[sorted_t.length - 1],
    most_mem_efficient: sorted_m[0],
    most_mem_intensive: sorted_m[sorted_m.length - 1],
    leaky: benchmarks.filter(b => b.memory.max_leaked_mb > 10),
  };
}

// ── ASP diagnostic analytics ──────────────────────────────────────────────────

/** Per-dataset alignment drift profile: dy_steps / dx_steps coeff-of-variation. */
export interface AlignmentDriftEntry {
  dataset: string;
  dy_steps: number[];
  dx_steps: number[];
  dy_cv: number;
  dx_cv: number;
  is_horizontal_scroll: boolean;
  used_fallback: boolean;
}

export function computeAlignmentDrift(datasets: AspDataset[]): AlignmentDriftEntry[] {
  return datasets
    .filter(ds => ds.alignment != null)
    .map(ds => {
      const al = ds.alignment!;
      return {
        dataset: ds.name,
        dy_steps: al.dy_steps,
        dx_steps: al.dx_steps,
        dy_cv: al.dy_cv,
        dx_cv: al.dx_cv,
        is_horizontal_scroll: al.dx_cv < al.dy_cv,
        used_fallback: ds.used_fallback,
      };
    });
}

/** Photometric correction profile per dataset: gain applied per frame. */
export interface PhotometricProfileEntry {
  dataset: string;
  frame_index: number;
  bg_lum: number | null;
  applied_gain: number;
  ref_lum: number | null;
}

export function computePhotometricProfile(datasets: AspDataset[]): PhotometricProfileEntry[] {
  const result: PhotometricProfileEntry[] = [];
  for (const ds of datasets) {
    if (!ds.photometric) continue;
    const p = ds.photometric;
    const n = Math.max(p.bg_lums.length, p.applied_gains.length);
    for (let i = 0; i < n; i++) {
      result.push({
        dataset: ds.name,
        frame_index: i,
        bg_lum: p.bg_lums[i] ?? null,
        applied_gain: p.applied_gains[i] ?? 1.0,
        ref_lum: p.ref_lum ?? null,
      });
    }
  }
  return result;
}

/** Per-seam quality breakdown: ghost, NCC, color score per boundary index. */
export interface PerSeamQualityEntry {
  dataset: string;
  seam_index: number;
  ghost_score: number | null;
  ncc_score: number | null;
  color_score: number | null;
  worst_metric: 'ghost' | 'ncc' | 'color' | null;
}

export function computePerSeamDetail(datasets: AspDataset[]): PerSeamQualityEntry[] {
  const result: PerSeamQualityEntry[] = [];
  for (const ds of datasets) {
    const m = ds.metrics_asp;
    if (!m) continue;
    const n = Math.max(
      m.ghost_seam_scores?.length ?? 0,
      m.seam_ncc_scores?.length ?? 0,
      m.seam_color_scores?.length ?? 0,
    );
    if (n === 0) continue;
    for (let i = 0; i < n; i++) {
      const ghost = m.ghost_seam_scores?.[i] ?? null;
      const ncc = m.seam_ncc_scores?.[i] ?? null;
      const color = m.seam_color_scores?.[i] ?? null;
      // Worst metric: ghost>30 is bad, ncc<0.5 is bad (normalized to [0,1] both higher=better)
      const ghostNorm = ghost != null ? Math.max(0, 1 - ghost / 100) : null;
      const nccNorm = ncc != null ? (ncc + 1) / 2 : null;
      const colorNorm = color ?? null;
      const normed = [
        { k: 'ghost' as const, v: ghostNorm },
        { k: 'ncc' as const, v: nccNorm },
        { k: 'color' as const, v: colorNorm },
      ].filter(x => x.v != null);
      const worst = normed.length > 0
        ? normed.reduce((a, b) => (a.v! < b.v! ? a : b)).k
        : null;
      result.push({ dataset: ds.name, seam_index: i, ghost_score: ghost, ncc_score: ncc, color_score: color, worst_metric: worst });
    }
  }
  return result;
}

/** Edge quality breakdown: match weight distribution and affine health per dataset. */
export interface EdgeQualityEntry {
  dataset: string;
  health_valid: boolean;
  health_ratio: number;
  health_reason: string;
  min_gap_px: number;
  max_rotation: number;
  max_scale_dev: number;
  used_fallback: boolean;
}

export function computeEdgeQualityBreakdown(datasets: AspDataset[]): EdgeQualityEntry[] {
  return datasets
    .filter(ds => ds.affine_health != null)
    .map(ds => {
      const h = ds.affine_health!;
      return {
        dataset: ds.name,
        health_valid: h.valid,
        health_ratio: h.ratio,
        health_reason: h.reason,
        min_gap_px: h.min_gap_px,
        max_rotation: h.max_rotation,
        max_scale_dev: h.max_scale_dev,
        used_fallback: ds.used_fallback,
      };
    });
}

/** Frame selection funnel: original → smart_select → spatial_dedup → final. */
export interface FrameSelectionEntry {
  dataset: string;
  original_count: number;
  smart_select_count: number;
  spatial_dedup_count: number;
  final_count: number;
  frames_dropped_smart: number;
  frames_dropped_dedup: number;
  selection_mode: string;
  drop_pct: number;
}

export function computeFrameSelectionStats(datasets: AspDataset[]): FrameSelectionEntry[] {
  return datasets
    .filter(ds => ds.frame_selection != null)
    .map(ds => {
      const f = ds.frame_selection!;
      const drop_pct = f.original_count > 0
        ? ((f.original_count - f.final_count) / f.original_count) * 100
        : 0;
      return { dataset: ds.name, ...f, drop_pct };
    });
}

/** Fallback reason distribution across all datasets in a report set. */
export interface FallbackReasonEntry {
  reason_class: string;   // e.g. "alignment_failed", "composite_gate_sc", "ghost_gate", "render_exception", "none"
  count: number;
  pct: number;
  datasets: string[];
}

export function computeFallbackReasonDistribution(datasets: AspDataset[]): FallbackReasonEntry[] {
  const groups: Record<string, string[]> = {};
  for (const ds of datasets) {
    const key = ds.fallback_reason
      ? ds.fallback_reason.split(':')[0]
      : 'none';
    if (!groups[key]) groups[key] = [];
    groups[key].push(ds.name);
  }
  const total = datasets.length || 1;
  return Object.entries(groups).map(([reason_class, dsets]) => ({
    reason_class,
    count: dsets.length,
    pct: (dsets.length / total) * 100,
    datasets: dsets,
  })).sort((a, b) => b.count - a.count);
}

/** GT comparison table: SSIM/PSNR/aligned-SSIM deltas vs ground truth. */
export interface GtComparisonEntry {
  dataset: string;
  ssim_vs_gt: number | null;
  aligned_ssim_vs_gt: number | null;
  psnr_vs_gt: number | null;
  verdict: string | null;
  used_fallback: boolean;
}

export function computeGtComparisons(datasets: AspDataset[]): GtComparisonEntry[] {
  return datasets
    .filter(ds => ds.ground_truth != null)
    .map(ds => ({
      dataset: ds.name,
      ssim_vs_gt: ds.ground_truth!.ssim_vs_gt ?? null,
      aligned_ssim_vs_gt: ds.ground_truth!.aligned_ssim_vs_gt ?? null,
      psnr_vs_gt: ds.ground_truth!.psnr_vs_gt ?? null,
      verdict: ds.ground_truth!.verdict ?? null,
      used_fallback: ds.used_fallback,
    }));
}
