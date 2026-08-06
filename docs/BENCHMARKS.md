# Engine correctness and performance baselines

The deterministic baseline covers every current engine area: scribble and
reference colorization, temporal propagation, and ARAP deformation. Synthetic
fixtures avoid licensing ambiguity and run without CUDA. Small expected arrays
are committed directly under `benchmark/goldens/`.

Run the correctness tests with `uv run pytest test/benchmark`. Capture a local
performance report with:

```bash
uv run python benchmark/run_baseline.py \
  --repeats 5 \
  --hardware-class "Desktop CPU; RTX 3090 Ti class (unused)"
```

Reports contain only the OS/architecture class, Python version, and the supplied
broad hardware class—never hostname, username, device serial, or exact machine
identity. The manual `Engine baseline` workflow follows the same rule.

Each warmed case records median/minimum latency and peak Python-tracked memory.
The latter excludes native allocations and GPU memory and must not be presented
as whole-process memory. Future CUDA workloads must add peak VRAM independently.

Color outputs allow mean absolute error ≤0.25 and maximum channel error ≤2 to
accommodate legitimate OpenCV/SciPy platform variation. ARAP vertices allow mean
error ≤1e-6 pixels and maximum error ≤1e-5 pixels. These are regression bounds,
not perceptual-quality claims; openly licensed real-art fixtures and SSIM/edge
preservation metrics will supplement them later.

The first CPU-only run shows temporal propagation as the slowest and most
memory-intensive current workload, followed by scribble colorization. ARAP is
smaller and reference colorization is fastest at fixture scale. This evidence
does not yet justify rewriting any component in C++; larger representative
fixtures and native-allocation measurements are required first.
