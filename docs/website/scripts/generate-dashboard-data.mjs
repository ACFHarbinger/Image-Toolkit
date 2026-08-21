#!/usr/bin/env node
/**
 * Aggregate ASP automated benchmark runs + human evaluations into static
 * JSON consumed by the docs website dashboard.
 *
 * Inputs (relative to Image-Toolkit repo root):
 *   submodules/ASP/backend/benchmark/output/anime_stitch_*.json
 *   submodules/ASP/data/benchmarks/asp_evaluations_*.json
 *   data/benchmarks/asp_evaluations_*.json  (optional IT mirror)
 *
 * Outputs:
 *   docs/website/public/data/benchmark_results.json
 *   docs/website/public/data/asp_evaluations.json   (latest human ratings snapshot)
 *   docs/website/public/data/dashboard_meta.json
 *
 * Usage (from repo root or docs/website):
 *   node docs/website/scripts/generate-dashboard-data.mjs
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEBSITE_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(WEBSITE_ROOT, "../..");
const OUT_DIR = path.join(WEBSITE_ROOT, "public", "data");

const RUN_GLOBS = [
  path.join(REPO_ROOT, "submodules/ASP/backend/benchmark/output"),
  path.join(REPO_ROOT, "backend/benchmark/results"),
  path.join(REPO_ROOT, "backend/benchmark/output"),
];

const EVAL_DIRS = [
  path.join(REPO_ROOT, "submodules/ASP/data/benchmarks"),
  path.join(REPO_ROOT, "data/benchmarks"),
];

// M2 audit status is deliberately checked into the generated contract rather
// than inferred by the UI.  These are diagnostics, not automated quality
// verdict weights; human preference and GT comparisons remain separate.
const AUTOMATED_METRIC_CATALOG = {
  cqas_v1_legacy: {
    label: "CQAS v1 (legacy diagnostic)",
    direction: "higher_is_better_historically",
    status: "legacy_diagnostic_only",
    verdict_eligible: false,
    note: "Failed human-label correlation audit; never use for ranking or X-wins claims.",
  },
  seam_visibility: {
    label: "Seam visibility",
    direction: "lower_is_better",
    status: "human_aligned_candidate",
    verdict_eligible: true,
  },
  seam_gradient: {
    label: "Seam gradient",
    direction: "lower_is_better",
    status: "human_aligned_supporting_diagnostic",
    verdict_eligible: false,
  },
  ghosting_siqe: {
    label: "Ghosting SIQE",
    direction: "lower_is_better_historically",
    status: "inverse_validated_telemetry",
    verdict_eligible: false,
  },
  seam_coherence: {
    label: "Seam coherence / banding",
    direction: "lower_is_better_historically",
    status: "no_human_correlation_telemetry",
    verdict_eligible: false,
  },
  strip_banding_score: {
    label: "Strip banding",
    direction: "lower_is_better_historically",
    status: "inverse_validated_telemetry",
    verdict_eligible: false,
  },
};

function listMatching(dir, prefix, suffix = ".json") {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir)
    .filter((f) => f.startsWith(prefix) && f.endsWith(suffix))
    .map((f) => path.join(dir, f))
    .sort();
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

function normalizeMetricsForDashboard(metrics) {
  if (!metrics || typeof metrics !== "object") return null;
  const normalized = { ...metrics };
  // Older benchmark artifacts used an unversioned name. Preserve the value for
  // historical inspection but prevent consumers from mistaking it for a live
  // aggregate quality score.
  if (normalized.cqas_v1_legacy == null && normalized.cqas != null) {
    normalized.cqas_v1_legacy = normalized.cqas;
  }
  delete normalized.cqas;
  return normalized;
}

function summarizeRun(filePath, raw) {
  const meta = raw.metadata || {};
  const summary = raw.summary || {};
  const system = raw.system || {};
  // Derive timestamp from filename anime_stitch_YYYYMMDD_HHMMSS.json
  const base = path.basename(filePath, ".json");
  const m = base.match(/(\d{8})_(\d{6})$/);
  const timestamp = m
    ? `${m[1].slice(0, 4)}-${m[1].slice(4, 6)}-${m[1].slice(6, 8)}T${m[2].slice(0, 2)}:${m[2].slice(2, 4)}:${m[2].slice(4, 6)}`
    : meta.timestamp || null;

  // Compact per-dataset slice for charts (keep small)
  const datasets = Array.isArray(raw.datasets)
    ? raw.datasets.map((d) => ({
        name: d.name,
        used_fallback: Boolean(d.used_fallback),
        fallback_reason: d.fallback_reason || null,
        time: d.time || null,
        metrics_asp: normalizeMetricsForDashboard(d.metrics_asp),
        metrics_simple: normalizeMetricsForDashboard(d.metrics_simple),
        comparison: d.comparison || null,
        human_coherence: d.human_coherence || null,
      }))
    : [];

  return {
    id: base,
    source: path.relative(REPO_ROOT, filePath),
    timestamp,
    metadata: {
      git_commit: meta.git_commit || meta.commit || null,
      label: meta.label || meta.experiment_label || null,
    },
    system: {
      gpu: system.gpu || system.device || null,
      cuda: system.cuda || null,
    },
    summary: {
      total_datasets: summary.total_datasets ?? datasets.length,
      datasets_passed: summary.datasets_passed ?? null,
      datasets_fallback: summary.datasets_fallback ?? null,
      total_time_sec: summary.total_time_sec ?? null,
      avg_time_per_dataset_sec: summary.avg_time_per_dataset_sec ?? null,
      avg_sharpness_asp: summary.avg_sharpness_asp ?? null,
      avg_sharpness_simple: summary.avg_sharpness_simple ?? null,
      avg_ghosting_asp: summary.avg_ghosting_asp ?? null,
      avg_ghosting_simple: summary.avg_ghosting_simple ?? null,
      avg_coverage_asp: summary.avg_coverage_asp ?? null,
      avg_ssim: summary.avg_ssim ?? null,
      verdict_counts: summary.verdict_counts || null,
      gt_verdict_counts: summary.gt_verdict_counts || null,
      avg_ssim_asp_vs_gt: summary.avg_ssim_asp_vs_gt ?? null,
      avg_ssim_simple_vs_gt: summary.avg_ssim_simple_vs_gt ?? null,
      human_coherence_rated: summary.human_coherence_rated ?? null,
    },
    automated_metric_catalog: AUTOMATED_METRIC_CATALOG,
    datasets,
  };
}

function summarizeEvaluations(evalMap) {
  const entries = Object.entries(evalMap || {});
  const reviewed = entries.filter(
    ([, e]) => e && (e.reviewed || e.asp != null || e.simple != null)
  );
  const aspScores = reviewed.map(([, e]) => e.asp).filter((n) => typeof n === "number");
  const simpleScores = reviewed
    .map(([, e]) => e.simple)
    .filter((n) => typeof n === "number");
  const prefs = {};
  for (const [, e] of reviewed) {
    const p = e.preference || "unset";
    prefs[p] = (prefs[p] || 0) + 1;
  }
  const mean = (arr) =>
    arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;
  // How often simple wins on preference
  const prefSimple = prefs.simple || 0;
  const prefAsp = prefs.asp || 0;
  return {
    total_keys: entries.length,
    reviewed: reviewed.length,
    mean_asp: mean(aspScores),
    mean_simple: mean(simpleScores),
    preference_counts: prefs,
    preference_simple_share:
      prefSimple + prefAsp > 0 ? prefSimple / (prefSimple + prefAsp) : null,
    // Explicit product signal for Harbinger's rating pass (2026-08-10):
    // human structural judgment currently favors SCANS/simple on most cases.
    narrative_hint:
      prefSimple > prefAsp
        ? "Human ratings currently prefer OpenCV SCANS (simple) more often than ASP."
        : prefAsp > prefSimple
          ? "Human ratings currently prefer ASP more often than simple."
          : "Human preference split is even or unrated.",
  };
}

function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const runFiles = RUN_GLOBS.flatMap((dir) => listMatching(dir, "anime_stitch_"));
  const runs = [];
  for (const f of runFiles) {
    try {
      runs.push(summarizeRun(f, readJson(f)));
    } catch (e) {
      console.warn("skip run", f, e.message);
    }
  }

  const evalFiles = EVAL_DIRS.flatMap((dir) => listMatching(dir, "asp_evaluations_"));
  // also accept undated snapshot names
  for (const dir of EVAL_DIRS) {
    const snap = path.join(dir, "asp_evaluations.json");
    if (fs.existsSync(snap)) evalFiles.push(snap);
  }
  const uniqueEval = [...new Set(evalFiles)].sort();
  let latestEval = {};
  let latestEvalPath = null;
  if (uniqueEval.length) {
    latestEvalPath = uniqueEval[uniqueEval.length - 1];
    latestEval = readJson(latestEvalPath);
  }

  const benchmark_results = {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    run_count: runs.length,
    runs,
  };

  const human_snapshot = {
    schema_version: 1,
    generated_at: new Date().toISOString(),
    source: latestEvalPath ? path.relative(REPO_ROOT, latestEvalPath) : null,
    summary: summarizeEvaluations(latestEval),
    // Flat map for dashboard compatibility with RatingsDashboardView
    evaluations: latestEval,
  };

  // Write dashboard-compatible flat map for the Vue/React ratings view
  fs.writeFileSync(
    path.join(OUT_DIR, "asp_evaluations.json"),
    JSON.stringify(latestEval, null, 2) + "\n"
  );
  fs.writeFileSync(
    path.join(OUT_DIR, "benchmark_results.json"),
    JSON.stringify(benchmark_results, null, 2) + "\n"
  );
  fs.writeFileSync(
    path.join(OUT_DIR, "human_ratings_summary.json"),
    JSON.stringify(human_snapshot, null, 2) + "\n"
  );
  fs.writeFileSync(
    path.join(OUT_DIR, "dashboard_meta.json"),
    JSON.stringify(
      {
        generated_at: new Date().toISOString(),
        automated_runs: runs.length,
        human_eval_source: human_snapshot.source,
        human_summary: human_snapshot.summary,
        notes: [
          "Human coherence scores are not interchangeable with SSIM/sharpness/ghosting.",
          "CQAS v1 is retained only as a legacy diagnostic; it is excluded from rankings and X-wins claims.",
          "Harbinger rating pass (2026-08-10): ASP often loses to OpenCV SCANS on structural coherence — banding, color shifts, seam degradation vs SCANS mild ghosting.",
        ],
      },
      null,
      2
    ) + "\n"
  );

  // Generate M2.5a (#32) Per-Defect & Stage-Attributed Correlation Matrix
  const defectAuditScript = path.join(
    REPO_ROOT,
    "submodules/ASP/backend/benchmark/audit_defect_correlation.py"
  );
  const subsetSelectionScript = path.join(
    REPO_ROOT,
    "submodules/ASP/backend/benchmark/subset_selection.py"
  );
  const primaryRunFile = runFiles.find((f) => path.basename(f) === "anime_stitch_20260807_045552.json") || runFiles[0];
  if (primaryRunFile && latestEvalPath) {
    const pythonBin = fs.existsSync(path.join(REPO_ROOT, ".venv/bin/python"))
      ? path.join(REPO_ROOT, ".venv/bin/python")
      : "python3";
    
    if (fs.existsSync(defectAuditScript)) {
      try {
        const defectJsonOut = path.join(OUT_DIR, "defect_correlation_matrix.json");
        import("node:child_process").then(({ execFileSync }) => {
          execFileSync(pythonBin, [
            defectAuditScript,
            "--run",
            primaryRunFile,
            "--labels",
            latestEvalPath,
            "--json-out",
            defectJsonOut,
          ]);
          console.log("generated defect correlation matrix:", defectJsonOut);
        }).catch((e) => {
          console.warn("failed to run defect correlation script:", e.message);
        });
      } catch (e) {
        console.warn("could not spawn defect correlation audit:", e.message);
      }
    }

    if (fs.existsSync(subsetSelectionScript)) {
      try {
        const subsetJsonOut = path.join(OUT_DIR, "benchmark_subsets.json");
        import("node:child_process").then(({ execFileSync }) => {
          execFileSync(pythonBin, [
            subsetSelectionScript,
            "--run",
            primaryRunFile,
            "--labels",
            latestEvalPath,
            "--mode",
            "all_standard",
            "--json-out",
            subsetJsonOut,
          ]);
          console.log("generated benchmark subsets:", subsetJsonOut);
        }).catch((e) => {
          console.warn("failed to run subset selection script:", e.message);
        });
      } catch (e) {
        console.warn("could not spawn subset selection:", e.message);
      }
    }

    const coherenceV2Script = path.join(
      REPO_ROOT,
      "submodules/ASP/backend/benchmark/bench_coherence_v2_ab.py"
    );
    if (fs.existsSync(coherenceV2Script)) {
      try {
        const abJsonOut = path.join(OUT_DIR, "coherence_v2_ab_eval.json");
        import("node:child_process").then(({ execFileSync }) => {
          execFileSync(pythonBin, [
            coherenceV2Script,
            "--labels",
            latestEvalPath,
            "--json-out",
            abJsonOut,
          ]);
          console.log("generated coherence_v2 A/B evaluation:", abJsonOut);
        }).catch((e) => {
          console.warn("failed to run coherence_v2 A/B eval script:", e.message);
        });
      } catch (e) {
        console.warn("could not spawn coherence_v2 A/B eval:", e.message);
      }
    }
  }

  console.log(
    `dashboard data: ${runs.length} automated run(s), human eval keys=${Object.keys(latestEval).length}`
  );
  if (human_snapshot.summary.narrative_hint) {
    console.log("human signal:", human_snapshot.summary.narrative_hint);
  }
  console.log("wrote", OUT_DIR);
}

main();
