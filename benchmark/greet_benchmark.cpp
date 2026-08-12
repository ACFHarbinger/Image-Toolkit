#include <benchmark/benchmark.h>

#include "single_module_template/greet.hpp"

static void BM_Greet(benchmark::State& state) {
    for (auto _ : state) {
        benchmark::DoNotOptimize(single_module_template::greet("world"));
    }
}
BENCHMARK(BM_Greet);
