// Sourced verbatim from docs/BENCHMARKS.md's "Benchmark Suite Index" table —
// feeds the Roadmap/Stats hub panel. Kept hand-curated rather than parsed at
// build time so the table stays a stable, reviewable list even if the doc's
// prose around it changes.
import type { BenchmarkSuite } from "../interfaces/types";

export const benchmarkSuites: BenchmarkSuite[] = [
  {
    suite: "Database",
    runner: "Python benchmark/bench_database.py",
    location: "backend/benchmark/",
    output: "results/benchmark_*.json",
    ciJob: "benchmark.yml",
  },
  {
    suite: "ML Models",
    runner: "Python benchmark/bench_models.py",
    location: "backend/benchmark/",
    output: "results/benchmark_*.json",
    ciJob: "benchmark.yml",
  },
  {
    suite: "Image Processing",
    runner: "Python benchmark/bench_image_ops.py",
    location: "backend/benchmark/",
    output: "results/benchmark_*.json",
    ciJob: "benchmark.yml",
  },
  {
    suite: "C++ Base",
    runner: "just test-base-cpp",
    location: "base/tests/",
    output: "ctest output",
    ciJob: "benchmark.yml",
  },
  {
    suite: "ASP Corpus",
    runner: "backend/benchmark/bench_anime_stitch.py",
    location: "backend/benchmark/",
    output: "data/output/benchmark_report.md",
    ciJob: "manual",
  },
  {
    suite: "Frontend Math",
    runner: "npm test / TypeDoc",
    location: "frontend/src/math/",
    output: "Jest output",
    ciJob: "docs.yml (type-check)",
  },
];
