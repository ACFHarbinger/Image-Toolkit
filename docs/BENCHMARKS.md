# Benchmarks

Micro-benchmarks use **Google Benchmark** to measure performance of core functions.

| Target | Tool | Location |
| --- | --- | --- |
| `hybrid_image_editor_benchmark` | Google Benchmark | `logic/benchmark/greet_benchmark.cpp` |

Run benchmarks with:

```bash
just bench
# Or directly via cmake:
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_BENCHMARK=ON
cmake --build build --target hybrid_image_editor_benchmark
./build/logic/benchmark/hybrid_image_editor_benchmark
```
