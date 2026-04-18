"""
Benchmark utilities for measuring memory and time across backend operations.
"""

import os
import gc
import time
import psutil
import json
from typing import Callable, Any, Dict, List, Optional
from functools import wraps
from datetime import datetime
from pathlib import Path


class MemoryTracker:
    """Tracks memory usage for a code block."""

    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.baseline = 0
        self.peak = 0
        self.samples = []

    def start(self):
        """Start tracking memory."""
        gc.collect()
        time.sleep(0.1)  # Let GC finish
        self.baseline = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak = self.baseline
        self.samples = [self.baseline]

    def sample(self):
        """Take a memory sample."""
        current = self.process.memory_info().rss / 1024 / 1024
        self.samples.append(current)
        if current > self.peak:
            self.peak = current

    def stop(self):
        """Stop tracking and return stats."""
        gc.collect()
        time.sleep(0.1)
        final = self.process.memory_info().rss / 1024 / 1024

        return {
            "baseline_mb": round(self.baseline, 2),
            "peak_mb": round(self.peak, 2),
            "final_mb": round(final, 2),
            "delta_mb": round(self.peak - self.baseline, 2),
            "leaked_mb": round(final - self.baseline, 2),
        }


def measure_memory(func: Callable) -> Callable:
    """Decorator to measure memory usage of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        tracker = MemoryTracker()
        tracker.start()

        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start_time

        mem_stats = tracker.stop()

        return {
            "result": result,
            "time_sec": round(elapsed, 4),
            "memory": mem_stats
        }
    return wrapper


class BenchmarkRunner:
    """Manages benchmark execution and result collection."""

    def __init__(self, suite_name: str):
        self.suite_name = suite_name
        self.results: List[Dict[str, Any]] = []
        self.system_info = self._get_system_info()

    def _get_system_info(self) -> Dict[str, Any]:
        """Collect system information."""
        import platform
        import torch

        info = {
            "timestamp": datetime.now().isoformat(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu": platform.processor(),
            "cpu_count": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
        }

        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
            info["cuda_version"] = torch.version.cuda
            info["vram_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1)
        else:
            info["gpu"] = "None (CPU only)"

        return info

    def benchmark(self, name: str, iterations: int = 1, warmup: int = 0):
        """Decorator to register a benchmark."""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Warmup runs
                for _ in range(warmup):
                    func(*args, **kwargs)
                    gc.collect()

                # Benchmark runs
                times = []
                memory_samples = []

                for i in range(iterations):
                    tracker = MemoryTracker()
                    tracker.start()

                    start = time.perf_counter()
                    result = func(*args, **kwargs)
                    elapsed = time.perf_counter() - start

                    mem_stats = tracker.stop()

                    times.append(elapsed)
                    memory_samples.append(mem_stats)

                    # Clean up between iterations
                    if i < iterations - 1:
                        del result
                        gc.collect()
                        time.sleep(0.05)

                # Aggregate stats
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)

                avg_peak_mem = sum(m["peak_mb"] for m in memory_samples) / len(memory_samples)
                max_peak_mem = max(m["peak_mb"] for m in memory_samples)
                avg_delta_mem = sum(m["delta_mb"] for m in memory_samples) / len(memory_samples)
                max_leaked = max(m["leaked_mb"] for m in memory_samples)

                bench_result = {
                    "name": name,
                    "iterations": iterations,
                    "time": {
                        "avg_sec": round(avg_time, 4),
                        "min_sec": round(min_time, 4),
                        "max_sec": round(max_time, 4),
                        "total_sec": round(sum(times), 4),
                    },
                    "memory": {
                        "avg_peak_mb": round(avg_peak_mem, 2),
                        "max_peak_mb": round(max_peak_mem, 2),
                        "avg_delta_mb": round(avg_delta_mem, 2),
                        "max_leaked_mb": round(max_leaked, 2),
                    }
                }

                self.results.append(bench_result)
                return bench_result

            # Store the wrapper to call later
            self._registered_benchmarks = getattr(self, "_registered_benchmarks", [])
            self._registered_benchmarks.append((name, wrapper))

            return wrapper
        return decorator

    def run(self):
        """Run all registered benchmarks."""
        print(f"\n{'='*60}")
        print(f"{self.suite_name} — Started at {self.system_info['timestamp']}")
        print(f"{'='*60}\n")
        print(f"System: {self.system_info['platform']}")
        print(f"CPU: {self.system_info['cpu']} ({self.system_info['cpu_threads']} threads)")
        print(f"RAM: {self.system_info['ram_gb']} GB")
        print(f"GPU: {self.system_info['gpu']}\n")

        for name, bench_func in getattr(self, "_registered_benchmarks", []):
            print(f"Running: {name}...", end=" ", flush=True)
            bench_func()
            print("✓")

    def print_results(self):
        """Print formatted results to console."""
        if not self.results:
            print("No benchmark results to display.")
            return

        print(f"\n{'='*60}")
        print("Results Summary")
        print(f"{'='*60}\n")

        # Table header
        print(f"{'Benchmark':<40} {'Time (s)':<12} {'RAM (MB)':<12} {'Throughput':<15}")
        print(f"{'-'*40} {'-'*12} {'-'*12} {'-'*15}")

        for result in self.results:
            name = result["name"][:39]
            avg_time = result["time"]["avg_sec"]
            peak_mem = result["memory"]["avg_peak_mb"]

            # Calculate throughput if iterations > 1
            if result["iterations"] > 1:
                throughput = f"{result['iterations'] / result['time']['total_sec']:.1f} ops/sec"
            else:
                throughput = "—"

            print(f"{name:<40} {avg_time:<12.4f} {peak_mem:<12.2f} {throughput:<15}")

        # Peak RAM across all benchmarks
        max_ram = max(r["memory"]["max_peak_mb"] for r in self.results)
        print(f"\nPeak RAM across all benchmarks: {max_ram:.2f} MB")

    def save_json(self, output_path: Optional[Path] = None):
        """Save results to JSON file."""
        if output_path is None:
            output_dir = Path(__file__).parent / "results"
            output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = output_dir / f"benchmark_{timestamp}.json"

        output = {
            "suite": self.suite_name,
            "system": self.system_info,
            "results": self.results,
        }

        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\nResults saved to: {output_path}")
        return output_path

    def save_detailed_report(self, output_path: Optional[Path] = None):
        """Save detailed report with comprehensive statistics and metadata."""
        if output_path is None:
            output_dir = Path(__file__).parent / "results"
            output_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suite_slug = self.suite_name.lower().replace(" ", "_")
            output_path = output_dir / f"{suite_slug}_{timestamp}.json"

        # Calculate aggregate statistics
        total_time = sum(r["time"]["total_sec"] for r in self.results)
        avg_time = sum(r["time"]["avg_sec"] for r in self.results) / len(self.results) if self.results else 0
        max_peak_mem = max(r["memory"]["max_peak_mb"] for r in self.results) if self.results else 0
        total_leaked = sum(r["memory"]["max_leaked_mb"] for r in self.results) if self.results else 0

        output = {
            "metadata": {
                "suite_name": self.suite_name,
                "timestamp": self.system_info["timestamp"],
                "total_benchmarks": len(self.results),
                "total_time_sec": round(total_time, 4),
                "format_version": "1.0",
            },
            "system": self.system_info,
            "summary": {
                "total_execution_time_sec": round(total_time, 4),
                "avg_benchmark_time_sec": round(avg_time, 4),
                "max_peak_memory_mb": round(max_peak_mem, 2),
                "total_memory_leaked_mb": round(total_leaked, 2),
                "benchmarks_passed": len(self.results),
                "benchmarks_failed": 0,  # Can be enhanced to track failures
            },
            "benchmarks": self.results,
            "performance_insights": self._generate_insights(),
        }

        with open(output_path, "w") as f:
            json.dump(output, f, indent=2)

        print(f"\nDetailed report saved to: {output_path}")
        return output_path

    def _generate_insights(self) -> Dict[str, Any]:
        """Generate performance insights from benchmark results."""
        if not self.results:
            return {}

        insights = {
            "slowest_benchmark": None,
            "fastest_benchmark": None,
            "most_memory_intensive": None,
            "most_memory_efficient": None,
            "potential_memory_leaks": [],
        }

        # Find slowest and fastest
        sorted_by_time = sorted(self.results, key=lambda r: r["time"]["avg_sec"])
        insights["fastest_benchmark"] = {
            "name": sorted_by_time[0]["name"],
            "avg_time_sec": sorted_by_time[0]["time"]["avg_sec"],
        }
        insights["slowest_benchmark"] = {
            "name": sorted_by_time[-1]["name"],
            "avg_time_sec": sorted_by_time[-1]["time"]["avg_sec"],
        }

        # Find memory intensive/efficient
        sorted_by_mem = sorted(self.results, key=lambda r: r["memory"]["avg_peak_mb"])
        insights["most_memory_efficient"] = {
            "name": sorted_by_mem[0]["name"],
            "avg_peak_mb": sorted_by_mem[0]["memory"]["avg_peak_mb"],
        }
        insights["most_memory_intensive"] = {
            "name": sorted_by_mem[-1]["name"],
            "avg_peak_mb": sorted_by_mem[-1]["memory"]["avg_peak_mb"],
        }

        # Detect potential memory leaks (leaked > 10MB)
        for result in self.results:
            if result["memory"]["max_leaked_mb"] > 10.0:
                insights["potential_memory_leaks"].append({
                    "name": result["name"],
                    "leaked_mb": result["memory"]["max_leaked_mb"],
                })

        return insights

    def check_regression(self, baseline_path: Path, threshold_time: float = 0.20, threshold_mem: float = 0.15):
        """Compare results against a baseline and detect regressions."""
        with open(baseline_path, "r") as f:
            baseline = json.load(f)

        baseline_map = {r["name"]: r for r in baseline["results"]}

        print(f"\n{'='*60}")
        print("Regression Analysis")
        print(f"{'='*60}\n")

        regressions = []

        for result in self.results:
            name = result["name"]
            if name not in baseline_map:
                print(f"⚠️  {name}: No baseline found (new benchmark)")
                continue

            base = baseline_map[name]

            time_delta = (result["time"]["avg_sec"] - base["time"]["avg_sec"]) / base["time"]["avg_sec"]
            mem_delta = (result["memory"]["avg_peak_mb"] - base["memory"]["avg_peak_mb"]) / base["memory"]["avg_peak_mb"]

            status = "✓"
            if time_delta > threshold_time:
                status = "⚠️ TIME REGRESSION"
                regressions.append((name, "time", time_delta))
            elif mem_delta > threshold_mem:
                status = "⚠️ MEMORY REGRESSION"
                regressions.append((name, "memory", mem_delta))
            elif time_delta < -0.10 or mem_delta < -0.10:
                status = "✨ IMPROVEMENT"

            print(f"{status:<20} {name:<30} Time: {time_delta:+.1%}  RAM: {mem_delta:+.1%}")

        if regressions:
            print(f"\n❌ {len(regressions)} regression(s) detected!")
            return False
        else:
            print("\n✅ All benchmarks passed (no regressions)")
            return True
