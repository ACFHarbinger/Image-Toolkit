#include <benchmark/benchmark.h>

#include "greet.hpp"

static void BM_Greet(benchmark::State& state) {
    for (auto _ : state) {
        benchmark::DoNotOptimize(hybrid_image_editor::greet("world"));
    }
}
BENCHMARK(BM_Greet);
