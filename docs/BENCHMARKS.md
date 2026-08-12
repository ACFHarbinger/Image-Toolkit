# Benchmarks

Micro-benchmarks use **Google Benchmark** to measure performance of core functions.

| Target | Tool | Location |
| --- | --- | --- |
| `single_module_template_benchmark` | Google Benchmark | `benchmark/greet_benchmark.cpp` |

Run benchmarks with:

```bash
just bench
# Or directly via cmake:
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_BENCHMARK=ON
cmake --build build --target single_module_template_benchmark
./build/benchmark/single_module_template_benchmark
```
