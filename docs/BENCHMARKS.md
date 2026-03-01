# Image-Toolkit Backend & Base Performance Benchmarks

Comprehensive benchmark suite for measuring memory usage and compute time across
the Python backend and Rust base layers.

## Prerequisites

```bash
# Install benchmark dependencies
pip install memory_profiler psutil pytest-benchmark matplotlib

# Ensure Rust benchmarks are enabled
cd ../base
cargo bench --features python
```

## Running Benchmarks

### Quick Start (All Benchmarks)

```bash
# Python backend benchmarks
python benchmark/run_all.py

# Rust base benchmarks
cd ../base
cargo bench --features python

# Combined report
python benchmark/generate_report.py
```

### Individual Benchmark Suites

```bash
# Database operations
python benchmark/bench_database.py

# ML model inference
python benchmark/bench_models.py

# Image processing (Python wrappers)
python benchmark/bench_image_ops.py

# Memory profiling only
python benchmark/memory_profile.py
```

## Benchmark Categories

### 1. Database Operations (`bench_database.py`)

- Tag insertion (1k, 10k tags)
- Group/subgroup operations
- Vector similarity search (100, 1k, 10k images)
- Bulk image insertion
- `fetchall()` vs `fetchmany()` comparison

**Metrics**: Query time, peak RAM, PostgreSQL buffer usage

### 2. ML Model Inference (`bench_models.py`)

- Siamese network (ResNet-18) embedding generation
- GAN (AnimeGAN2) single-image generation
- Stable Diffusion 3 (if model available)
- Model load/unload time
- CUDA vs CPU comparison

**Metrics**: Inference time, VRAM usage, CPU RAM, model load time

### 3. Image Processing (`bench_image_ops.py`)

- Image conversion (single, batch of 100/1000)
- Image merging (horizontal, vertical, grid)
- Video thumbnail generation
- Duplicate detection (pHash, SIFT, SSIM, ORB)

**Metrics**: Processing time, peak RAM, throughput (images/sec)

### 4. Rust Core Operations (`base/benches/*.rs`)

- File system scanning (1k, 10k, 100k files)
- Image conversion (Rust native)
- WebDriver crawler operations
- Cloud sync operations

**Metrics**: Execution time, peak RAM, allocations

## Output Formats

### Console Output (Real-time)

```
============================================================
Database Benchmarks — PostgreSQL 15.2, 10k test images
============================================================

Tag Operations:
  insert_tags_1k              0.234s    12.5 MB    4,273 tags/sec
  insert_tags_10k             2.156s    45.2 MB    4,638 tags/sec
  get_all_tags_fetchall       0.045s    2.1 MB     —
  get_all_tags_limit_1k       0.012s    0.5 MB     —

Vector Search:
  similarity_search_k10       0.089s    1.2 MB     112 queries/sec
  similarity_search_k100      0.234s    4.5 MB     —

Peak RAM: 125.4 MB
```

### JSON Report (`results/benchmark_YYYYMMDD_HHMMSS.json`)

```json
{
  "timestamp": "2026-03-01T14:23:45",
  "system": {
    "cpu": "AMD Ryzen 9 5950X",
    "ram": "64 GB",
    "gpu": "NVIDIA RTX 3090",
    "os": "Linux 6.18.0"
  },
  "benchmarks": {
    "database": { ... },
    "models": { ... },
    "image_ops": { ... },
    "rust_core": { ... }
  }
}
```

### HTML Report with Charts (`results/report.html`)

Interactive report with:
- Time-series comparison graphs
- Memory usage heatmaps
- Before/after optimization comparisons
- Regression detection

## Benchmark Data Setup

Run `benchmark/setup_test_data.py` to generate reproducible test datasets:

```bash
python benchmark/setup_test_data.py
```

This creates:
- `test_data/images/` — 1k synthetic images (various formats, sizes)
- `test_data/videos/` — 10 test videos (MP4, AVI)
- `test_data/database.sql` — 10k pre-seeded database entries
- `test_data/embeddings.npy` — Pre-computed embeddings for vector search

## Continuous Benchmarking

### GitHub Actions Integration

The `.github/workflows/benchmark.yml` workflow runs on:
- Every push to `main` (performance regression checks)
- Weekly schedule (long-term tracking)
- Manual trigger

Results are stored in `gh-pages` branch for historical comparison.

### Pre-commit Hook

```bash
# Install pre-commit benchmark (optional)
ln -s ../../benchmark/pre_commit_bench.py .git/hooks/pre-commit
```

Runs lightweight benchmarks before each commit, warns if performance degrades > 10%.

## Interpreting Results

### Memory Usage

- **Baseline**: Clean Python process + imported modules (~150 MB)
- **Acceptable growth**: < 500 MB for typical operations
- **Warning threshold**: > 1 GB for non-ML operations
- **Critical threshold**: > 4 GB (except SD3)

### Compute Time

- **Database queries**: < 100ms for single operations
- **Batch conversions**: > 50 images/sec (depends on size)
- **ML inference**:
  - Siamese: < 50ms/image (CPU), < 10ms (GPU)
  - GAN: < 1s/image (GPU)
  - SD3: 5–30s/image (depends on steps)

### Regression Criteria

A benchmark fails if:
- Memory usage increases > 15% vs baseline
- Execution time increases > 20% vs baseline
- Throughput decreases > 15% vs baseline

## Troubleshooting

**"psycopg2.OperationalError: could not connect to server"**
- Ensure PostgreSQL is running: `sudo systemctl start postgresql`
- Check connection params in `env/vars.env`

**"CUDA out of memory"**
- Reduce batch sizes in `bench_models.py`
- Set `CUDA_VISIBLE_DEVICES=""` to force CPU mode

**Rust benchmarks not found**
- Run `cargo build --release --features python` first
- Ensure `criterion` is in `Cargo.toml` dev-dependencies

## Adding New Benchmarks

### Python Backend

```python
# benchmark/bench_custom.py
from benchmark.utils import BenchmarkRunner, measure_memory

runner = BenchmarkRunner("Custom Operations")

@runner.benchmark("my_operation", iterations=100)
@measure_memory
def bench_my_op():
    # Your code here
    result = my_expensive_function()
    return result

if __name__ == "__main__":
    runner.run()
    runner.print_results()
```

### Rust Core

```rust
// base/benches/custom_bench.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use base::my_module::my_function;

fn benchmark_my_function(c: &mut Criterion) {
    c.bench_function("my_function", |b| {
        b.iter(|| my_function(black_box(input_data)))
    });
}

criterion_group!(benches, benchmark_my_function);
criterion_main!(benches);
```

## License

Same as parent project (see root LICENSE file).
