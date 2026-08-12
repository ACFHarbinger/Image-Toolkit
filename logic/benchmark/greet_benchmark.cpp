#include <benchmark/benchmark.h>

#include "hybrid_image_editor/greet.hpp"

static void BM_Greet(benchmark::State& state) {
    for (auto _ : state) {
        benchmark::DoNotOptimize(hybrid_image_editor::greet("world"));
    }
}
BENCHMARK(BM_Greet);
