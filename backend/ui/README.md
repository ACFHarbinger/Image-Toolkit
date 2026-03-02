# Benchmark Analysis Dashboard

Interactive Streamlit-based dashboard for analyzing Image-Toolkit benchmark results.

## Features

### 📊 Overview Page
- **Quick Summary**: View latest benchmark results across all suites
- **Performance Insights**: Automatically generated insights including:
  - Fastest/Slowest benchmarks
  - Most/Least memory-intensive operations
  - Potential memory leak detection

### 🔬 Suite Analysis
- **Detailed Metrics**: Deep dive into individual benchmark suites
- **Interactive Charts**: Plotly-powered visualizations for:
  - Execution time comparisons
  - Memory usage analysis
  - Statistical distributions
- **System Information**: Hardware and software configuration details
- **Data Export**: Download results as CSV for further analysis

### ⚖️ Function Comparison
- **Memory vs Time Analysis**: Interactive scatter plot showing the relationship between memory usage and execution time
  - Bubble size indicates efficiency (larger = less efficient)
  - Color coding shows performance (green = good, red = poor)
  - Logarithmic time scale for better visualization
- **Efficiency Ranking**: Automatic ranking of functions by combined time/memory efficiency
  - Color-coded performance indicators (green/yellow/red)
  - Displays top 3 most efficient and bottom 3 least efficient functions
- **Throughput Analysis**: Operations per second comparison across all benchmarks
- **Memory Breakdown**: Stacked visualization showing baseline memory, operation delta, and memory leaks
- **Comparison Table**: Comprehensive table with gradient coloring for easy identification of outliers
  - Time variance percentage
  - Throughput calculations
  - Memory efficiency metrics
- **Optimization Recommendations**: Automatic identification of functions needing performance improvements
  - Time optimization targets (>1.5x average)
  - Memory optimization targets (>70% of peak)

### 📈 Benchmark Trends
- **Historical Tracking**: Monitor benchmark performance over time
- **Regression Detection**: Identify performance degradation
- **Time-Series Visualization**: Dual-axis charts showing time and memory trends

### 🖥️ System Comparison
- **Cross-Platform Analysis**: Compare benchmark results across different machines
- **Configuration Impact**: See how CPU, GPU, and RAM affect performance

### 📄 Raw Data Viewer
- **JSON Explorer**: Browse raw benchmark data
- **Export Capability**: Download individual reports

## Usage

### Running Benchmarks with Reports

```bash
# Run all benchmarks and save detailed reports
just benchmark-save

# Run specific benchmark suite with reports
source .venv/bin/activate
python backend/benchmark/bench_thumbnails.py --save
python backend/benchmark/bench_database.py --save
python backend/benchmark/bench_models.py --save
```

### Launching the Dashboard

```bash
# Launch the interactive dashboard
just benchmark-dashboard
```

The dashboard will automatically open in your browser at `http://localhost:8501`

### Manual Installation (if needed)

```bash
# Install dashboard dependencies
pip install -r backend/ui/requirements.txt

# Run dashboard manually
streamlit run backend/ui/benchmark_dashboard.py
```

## Report Format

Benchmark reports are saved in JSON format to `backend/benchmark/results/` with the following structure:

```json
{
  "metadata": {
    "suite_name": "Database Operations",
    "timestamp": "2026-03-02T21:00:00",
    "total_benchmarks": 8,
    "total_time_sec": 45.23,
    "format_version": "1.0"
  },
  "system": {
    "platform": "Linux-6.18.0-9-generic",
    "python": "3.11.0",
    "cpu": "AMD Ryzen 9 5950X",
    "cpu_threads": 32,
    "ram_gb": 64.0,
    "gpu": "NVIDIA RTX 4090"
  },
  "summary": {
    "total_execution_time_sec": 45.23,
    "avg_benchmark_time_sec": 5.65,
    "max_peak_memory_mb": 2048.50,
    "total_memory_leaked_mb": 12.30,
    "benchmarks_passed": 8,
    "benchmarks_failed": 0
  },
  "benchmarks": [
    {
      "name": "vector_search_k10",
      "iterations": 10,
      "time": {
        "avg_sec": 0.234,
        "min_sec": 0.221,
        "max_sec": 0.289,
        "total_sec": 2.34
      },
      "memory": {
        "avg_peak_mb": 245.67,
        "max_peak_mb": 256.12,
        "avg_delta_mb": 12.34,
        "max_leaked_mb": 2.10
      }
    }
  ],
  "performance_insights": {
    "fastest_benchmark": {
      "name": "insert_tags_100",
      "avg_time_sec": 0.015
    },
    "slowest_benchmark": {
      "name": "vector_search_k100",
      "avg_time_sec": 1.234
    },
    "most_memory_efficient": {
      "name": "get_all_tags",
      "avg_peak_mb": 123.45
    },
    "most_memory_intensive": {
      "name": "bulk_image_insert_100",
      "avg_peak_mb": 512.34
    },
    "potential_memory_leaks": [
      {
        "name": "some_benchmark",
        "leaked_mb": 15.67
      }
    ]
  }
}
```

## Dashboard Components

### BenchmarkAnalyzer Class

The core analyzer that:
- Loads all JSON reports from `backend/benchmark/results/`
- Parses and validates report structure
- Generates interactive visualizations
- Computes derived metrics and insights

### Visualization Types

1. **Time Comparison Charts**: Bar charts with error bars showing min/avg/max execution times
2. **Memory Usage Charts**: Grouped bar charts comparing average and peak memory
3. **Trend Charts**: Dual-axis time-series showing performance evolution
4. **System Comparison Tables**: Sortable tables for cross-system analysis

## Performance Insights

The dashboard automatically detects:

- **Speed Champions**: Benchmarks that execute fastest
- **Speed Bottlenecks**: Slowest operations that need optimization
- **Memory Efficiency**: Operations with minimal memory footprint
- **Memory Hogs**: High-memory operations requiring attention
- **Memory Leaks**: Benchmarks that don't properly release memory (>10MB leaked)

## Tips

### Best Practices

1. **Run Multiple Times**: Execute benchmarks at least 3-5 times to establish reliable baselines
2. **Consistent Environment**: Run benchmarks on an idle system for accurate results
3. **Track Over Time**: Regular benchmark runs help identify performance regressions
4. **Document Changes**: Keep notes on what changed between benchmark runs

### Interpreting Results

- **Time Variations**: Error bars show min/max range; larger bars indicate inconsistent performance
- **Memory Leaks**: Any leak >10MB is flagged; investigate with profilers
- **Trends**: Upward trends in time/memory suggest regressions
- **System Impact**: GPU/CPU differences show parallelization effectiveness

## Troubleshooting

### Dashboard Won't Start

```bash
# Ensure Streamlit is installed
pip install -r backend/ui/requirements.txt

# Check for port conflicts
lsof -i :8501
```

### No Reports Found

```bash
# Verify reports exist
ls -lh backend/benchmark/results/

# Run benchmarks with --save flag
just benchmark-save
```

### Visualization Errors

- Ensure all required dependencies are installed
- Check that JSON reports are properly formatted
- Verify Python version >=3.11

## Architecture

```
backend/ui/
├── benchmark_dashboard.py    # Main Streamlit application
├── requirements.txt          # Dashboard dependencies
└── README.md                # This file

backend/benchmark/
├── utils.py                 # BenchmarkRunner with detailed reporting
├── bench_*.py              # Individual benchmark suites
├── run_all.py              # Master benchmark orchestrator
└── results/                # Generated JSON reports
    ├── database_operations_20260302_210000.json
    ├── thumbnail_generation_20260302_210500.json
    └── ml_model_inference_20260302_211000.json
```

## Future Enhancements

Potential features for future development:

- [ ] Automatic regression detection with alerts
- [ ] Comparison mode (before/after changes)
- [ ] Export to HTML/PDF reports
- [ ] Integration with CI/CD pipelines
- [ ] Real-time benchmark monitoring
- [ ] Custom alert thresholds
- [ ] Benchmark scheduling and automation
- [ ] Performance prediction using ML

## Contributing

When adding new benchmarks:

1. Use `@runner.benchmark()` decorator in your benchmark file
2. Call `runner.save_detailed_report()` to generate reports
3. The dashboard will automatically pick up new reports
4. Update this README if adding new visualization types

## License

Part of the Image-Toolkit project. See main project LICENSE.
