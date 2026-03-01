#!/usr/bin/env python3
"""
Master benchmark runner for Image-Toolkit backend and base.

Runs all benchmark suites and generates a combined report.
"""

import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# Benchmark modules
import bench_database
import bench_models


def run_python_benchmarks(save=False, baseline=None):
    """Run all Python backend benchmarks."""
    print("\n" + "="*60)
    print("PYTHON BACKEND BENCHMARKS")
    print("="*60)

    results = {}

    # Database benchmarks
    print("\n[1/2] Running database benchmarks...")
    try:
        bench_database.runner.run()
        bench_database.runner.print_results()
        if save:
            db_path = bench_database.runner.save_json()
            results["database"] = db_path
        if baseline:
            db_baseline = Path(baseline) / "database.json"
            if db_baseline.exists():
                bench_database.runner.check_regression(db_baseline)
    except Exception as e:
        print(f"❌ Database benchmarks failed: {e}")

    # Model benchmarks
    print("\n[2/2] Running ML model benchmarks...")
    try:
        bench_models.runner.run()
        bench_models.runner.print_results()
        if save:
            model_path = bench_models.runner.save_json()
            results["models"] = model_path
        if baseline:
            model_baseline = Path(baseline) / "models.json"
            if model_baseline.exists():
                bench_models.runner.check_regression(model_baseline)
    except Exception as e:
        print(f"❌ Model benchmarks failed: {e}")

    return results


def run_rust_benchmarks():
    """Run Rust core benchmarks using criterion."""
    print("\n" + "="*60)
    print("RUST CORE BENCHMARKS")
    print("="*60)

    base_dir = Path(__file__).parent.parent.parent / "base"

    try:
        print("\nBuilding and running Rust benchmarks...")
        result = subprocess.run(
            ["cargo", "bench", "--features", "python"],
            cwd=base_dir,
            capture_output=True,
            text=True,
        )

        print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode == 0:
            print("\n✓ Rust benchmarks completed successfully")
            # Criterion saves results to base/target/criterion/
            criterion_dir = base_dir / "target" / "criterion"
            return criterion_dir
        else:
            print(f"\n❌ Rust benchmarks failed with code {result.returncode}")
            return None
    except FileNotFoundError:
        print("❌ 'cargo' not found. Please install Rust toolchain.")
        return None
    except Exception as e:
        print(f"❌ Rust benchmarks failed: {e}")
        return None


def generate_combined_report(python_results, rust_results, output_dir):
    """Generate a combined HTML report from all benchmarks."""
    print("\n" + "="*60)
    print("GENERATING COMBINED REPORT")
    print("="*60)

    output_path = output_dir / f"benchmark_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    with open(output_path, "w") as f:
        f.write("""<!DOCTYPE html>
<html>
<head>
    <title>Image-Toolkit Performance Benchmarks</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background: #f5f5f5; }
        h1 { color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; border-bottom: 2px solid #ddd; padding-bottom: 5px; }
        .summary { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metric { display: inline-block; margin: 10px 20px; }
        .metric-label { font-weight: bold; color: #666; }
        .metric-value { font-size: 1.5em; color: #4CAF50; }
        table { width: 100%; border-collapse: collapse; background: white; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #4CAF50; color: white; font-weight: bold; }
        tr:hover { background: #f1f1f1; }
        .footer { margin-top: 40px; text-align: center; color: #999; font-size: 0.9em; }
        .benchmark-link { margin: 10px 0; }
        .benchmark-link a { color: #4CAF50; text-decoration: none; }
        .benchmark-link a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Image-Toolkit Performance Benchmarks</h1>
    <div class="summary">
        <h2>Benchmark Summary</h2>
        <div class="metric">
            <span class="metric-label">Generated:</span>
            <span class="metric-value">""" + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + """</span>
        </div>
""")

        # Python benchmarks
        f.write("""
        <h2>Python Backend Benchmarks</h2>
""")
        if python_results:
            for name, path in python_results.items():
                f.write(f"""
        <div class="benchmark-link">
            <a href="{path.relative_to(output_dir)}">{name.title()} Results (JSON)</a>
        </div>
""")
        else:
            f.write("<p>No Python benchmark results available.</p>")

        # Rust benchmarks
        f.write("""
        <h2>Rust Core Benchmarks</h2>
""")
        if rust_results and rust_results.exists():
            f.write(f"""
        <div class="benchmark-link">
            <a href="{rust_results.relative_to(output_dir)}/index.html">View Criterion Report</a>
        </div>
        <p>Detailed Rust benchmark results are available in the Criterion HTML reports.</p>
""")
        else:
            f.write("<p>No Rust benchmark results available.</p>")

        f.write("""
    </div>
    <div class="footer">
        Generated by Image-Toolkit benchmark suite
    </div>
</body>
</html>
""")

    print(f"\n✓ Combined report saved to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Run all Image-Toolkit benchmarks")
    parser.add_argument("--save", action="store_true", help="Save results to JSON")
    parser.add_argument("--baseline", type=Path, help="Directory with baseline results for regression check")
    parser.add_argument("--skip-python", action="store_true", help="Skip Python benchmarks")
    parser.add_argument("--skip-rust", action="store_true", help="Skip Rust benchmarks")
    parser.add_argument("--report", action="store_true", help="Generate combined HTML report")
    args = parser.parse_args()

    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    python_results = {}
    rust_results = None

    # Run Python benchmarks
    if not args.skip_python:
        python_results = run_python_benchmarks(save=args.save, baseline=args.baseline)

    # Run Rust benchmarks
    if not args.skip_rust:
        rust_results = run_rust_benchmarks()

    # Generate combined report
    if args.report:
        generate_combined_report(python_results, rust_results, results_dir)

    print("\n" + "="*60)
    print("ALL BENCHMARKS COMPLETE")
    print("="*60)


if __name__ == "__main__":
    main()
