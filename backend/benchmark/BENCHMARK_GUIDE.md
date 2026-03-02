# Benchmark Guide

Quick reference for running benchmarks and analyzing results.

## Running Benchmarks

### Quick Start

```bash
# Run all benchmarks and save detailed reports
just benchmark-save

# Launch the analysis dashboard
just benchmark-dashboard
```

### Individual Benchmarks

```bash
source .venv/bin/activate

# Database benchmarks
python backend/benchmark/bench_database.py --save

# Thumbnail generation benchmarks
python backend/benchmark/bench_thumbnails.py --save

# ML model benchmarks
python backend/benchmark/bench_models.py --save
```

## Benchmark Reports

Reports are automatically saved to `backend/benchmark/results/` with detailed JSON format containing:

- **Metadata**: Suite name, timestamp, total benchmarks
- **System Info**: CPU, GPU, RAM, platform details
- **Summary Statistics**: Total time, peak memory, leaks detected
- **Individual Benchmarks**: Time and memory metrics per test
- **Performance Insights**: Automated analysis of fastest/slowest, memory usage, potential leaks

### Report Naming

Reports use the format: `{suite_name}_{timestamp}.json`

Examples:
- `database_operations_20260302_210000.json`
- `thumbnail_generation_20260302_210500.json`
- `ml_model_inference_20260302_211000.json`

## Analysis Dashboard

### Features

The Streamlit dashboard provides:

1. **Overview**: Quick summary of latest results and insights
2. **Suite Analysis**: Deep dive into individual benchmark suites
3. **Benchmark Trends**: Historical performance tracking
4. **System Comparison**: Compare results across machines
5. **Raw Data**: Browse and export JSON reports

### Usage

```bash
# Launch dashboard
just benchmark-dashboard

# Access at http://localhost:8501
```

### Navigation

- Use sidebar to switch between pages
- Interactive charts support zoom, pan, and hover details
- Download data as CSV or JSON from any page

## Interpreting Results

### Time Metrics

- **avg_sec**: Average execution time across iterations
- **min_sec**: Fastest run (best case)
- **max_sec**: Slowest run (worst case)
- **total_sec**: Sum of all iterations

### Memory Metrics

- **avg_peak_mb**: Average peak memory during execution
- **max_peak_mb**: Highest memory usage observed
- **avg_delta_mb**: Average memory increase during operation
- **max_leaked_mb**: Memory not released after operation

### Performance Insights

The dashboard automatically identifies:

- ✅ **Fastest/Slowest**: Benchmarks by execution time
- ✅ **Memory Efficient/Intensive**: Operations by memory usage
- ⚠️ **Potential Leaks**: Benchmarks leaking >10MB

## Best Practices

1. **Baseline**: Run benchmarks before making changes
2. **Consistency**: Run on idle system for accurate results
3. **Multiple Runs**: Execute 3-5 times to establish patterns
4. **Track Changes**: Document what changed between runs
5. **Compare**: Use trends to identify regressions

## Example Workflow

```bash
# 1. Establish baseline
just benchmark-save

# 2. Make code changes
# ... edit code ...

# 3. Re-run benchmarks
just benchmark-save

# 4. Analyze results
just benchmark-dashboard

# 5. Compare trends in dashboard
# Navigate to "Benchmark Trends" page
# Select suite and benchmark to see historical comparison
```

## CI/CD Integration

For automated testing:

```bash
# Run with baseline comparison
python backend/benchmark/run_all.py --save --baseline baseline_results/

# Exit code 0 = pass, 1 = regression detected
```

## Troubleshooting

### No Reports in Dashboard

```bash
# Verify reports exist
ls backend/benchmark/results/

# Regenerate reports
just benchmark-save
```

### Streamlit Not Found

```bash
# Install dependencies
pip install -r backend/ui/requirements.txt
```

### Inconsistent Results

- Close other applications
- Disable power saving mode
- Run multiple iterations (increase in benchmark code)
- Check thermal throttling on CPU/GPU

## Advanced Usage

### Custom Benchmarks

Add new benchmarks to existing suites:

```python
@runner.benchmark("my_custom_benchmark", iterations=10, warmup=2)
@measure_memory
def bench_my_operation():
    # Your benchmark code here
    return result
```

### Regression Testing

```bash
# Save baseline
just benchmark-save
mv backend/benchmark/results/*.json baseline/

# After changes, compare
python backend/benchmark/run_all.py --save --baseline baseline/
```

### Export Options

From the dashboard:
- **CSV Export**: Download tables from "Suite Analysis" tab
- **JSON Export**: Download raw data from "Raw Data" page
- Charts can be saved as PNG using Plotly controls (camera icon)

## Performance Targets

General guidelines (system-dependent):

| Operation | Target Time | Target Memory |
|-----------|-------------|---------------|
| Tag Insert (100) | <0.1s | <50MB |
| Image Thumbnail | <0.05s | <100MB |
| Vector Search (k=10) | <0.5s | <200MB |
| Model Inference | <2s CPU, <0.5s GPU | <1GB |

## Additional Resources

- Main documentation: `backend/ui/README.md`
- Benchmark utilities: `backend/benchmark/utils.py`
- Individual suites: `backend/benchmark/bench_*.py`

---

**Quick Commands Reference**

```bash
just benchmark-save      # Run and save reports
just benchmark-dashboard # Launch dashboard
just benchmark          # Run without saving (console only)
```
