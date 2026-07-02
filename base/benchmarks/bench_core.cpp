// ---------------------------------------------------------------------------
// base/benchmarks/bench_core.cpp
//
// Google Benchmark suite for base::core:
//   • Filesystem scanning (flat + recursive)
//   • Single image conversion (PNG → WebP / JPEG)
//   • Batch image conversion (OpenMP parallel)
//   • Image merging: horizontal, vertical, grid
//
// Build:   cmake --build build/base --target base_bench_core
// Run:     ./build/base/benchmarks/base_bench_core --benchmark_format=json
// ---------------------------------------------------------------------------

#include <benchmark/benchmark.h>

#include "core/convert.hpp"
#include "core/filesystem.hpp"
#include "core/merger.hpp"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>

namespace fs = std::filesystem;
using namespace base::core;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static void write_png(const fs::path& p, int w, int h,
                      cv::Vec3b c = {100, 150, 200}) {
    cv::Mat img(h, w, CV_8UC3, cv::Scalar(c[0], c[1], c[2]));
    cv::imwrite(p.string(), img);
}

static std::vector<std::string> make_png_batch(const fs::path& dir,
                                                int count, int w, int h) {
    fs::create_directories(dir);
    std::vector<std::string> paths;
    paths.reserve(count);
    for (int i = 0; i < count; ++i) {
        auto p = dir / ("img_" + std::to_string(i) + ".png");
        write_png(p, w, h);
        paths.push_back(p.string());
    }
    return paths;
}

// ---------------------------------------------------------------------------
// Filesystem scan benchmarks
// ---------------------------------------------------------------------------

static void BM_ScanFlat(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    fs::path d  = fs::temp_directory_path() / ("bm_scan_flat_" + std::to_string(n));
    fs::remove_all(d);
    fs::create_directories(d);
    for (int i = 0; i < n; ++i)
        std::ofstream(d / ("f_" + std::to_string(i) + ".png")).put('\0');

    for (auto _ : state) {
        auto r = get_files_by_extension(d.string(), {".png"}, false);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * n);
    fs::remove_all(d);
}
BENCHMARK(BM_ScanFlat)->Arg(100)->Arg(500)->Arg(2000)->Unit(benchmark::kMicrosecond);

static void BM_ScanRecursive(benchmark::State& state) {
    const int n    = static_cast<int>(state.range(0));
    const int ndirs = 4;
    fs::path root   = fs::temp_directory_path() / ("bm_scan_rec_" + std::to_string(n));
    fs::remove_all(root);
    for (int d = 0; d < ndirs; ++d) {
        auto sub = root / ("d" + std::to_string(d));
        fs::create_directories(sub);
        for (int i = 0; i < n / ndirs; ++i)
            std::ofstream(sub / ("f_" + std::to_string(i) + ".png")).put('\0');
    }

    for (auto _ : state) {
        auto r = get_files_by_extension(root.string(), {".png"}, true);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * n);
    fs::remove_all(root);
}
BENCHMARK(BM_ScanRecursive)->Arg(200)->Arg(1000)->Unit(benchmark::kMicrosecond);

// ---------------------------------------------------------------------------
// Single-image conversion benchmarks (fixtures created once, reused)
// ---------------------------------------------------------------------------

struct ConvFix {
    fs::path tmp;
    std::string small_in, medium_in, large_in, out_base;
    ConvFix() {
        tmp = fs::temp_directory_path() / "bm_convert";
        fs::create_directories(tmp);
        small_in  = (tmp / "s.png").string();
        medium_in = (tmp / "m.png").string();
        large_in  = (tmp / "l.png").string();
        out_base  = (tmp / "out").string();
        write_png(tmp / "s.png",  256,  256);
        write_png(tmp / "m.png",  512,  512);
        write_png(tmp / "l.png", 1920, 1080);
    }
    ~ConvFix() { fs::remove_all(tmp); }
};
static ConvFix& cf() { static ConvFix f; return f; }

static bool do_convert(const std::string& in, const std::string& fmt) {
    std::string out = cf().out_base + "." + fmt;
    return convert_single_image(in, out, fmt, false, std::nullopt, "crop");
}

static void BM_ConvSmallWebp(benchmark::State& s) {
    for (auto _ : s) benchmark::DoNotOptimize(do_convert(cf().small_in,  "webp"));
}
BENCHMARK(BM_ConvSmallWebp)->Unit(benchmark::kMillisecond);

static void BM_ConvMediumWebp(benchmark::State& s) {
    for (auto _ : s) benchmark::DoNotOptimize(do_convert(cf().medium_in, "webp"));
}
BENCHMARK(BM_ConvMediumWebp)->Unit(benchmark::kMillisecond);

static void BM_ConvLargeWebp(benchmark::State& s) {
    for (auto _ : s) benchmark::DoNotOptimize(do_convert(cf().large_in,  "webp"));
}
BENCHMARK(BM_ConvLargeWebp)->Unit(benchmark::kMillisecond);

static void BM_ConvSmallJpeg(benchmark::State& s) {
    for (auto _ : s) benchmark::DoNotOptimize(do_convert(cf().small_in,  "jpg"));
}
BENCHMARK(BM_ConvSmallJpeg)->Unit(benchmark::kMillisecond);

static void BM_ConvLargeJpeg(benchmark::State& s) {
    for (auto _ : s) benchmark::DoNotOptimize(do_convert(cf().large_in,  "jpg"));
}
BENCHMARK(BM_ConvLargeJpeg)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// Batch conversion (OpenMP)
// ---------------------------------------------------------------------------

static void BM_ConvBatch(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    auto& f     = cf();
    fs::path bd = fs::path(f.tmp) / ("batch_" + std::to_string(n));
    fs::create_directories(bd);
    std::vector<std::pair<std::string, std::string>> pairs;
    pairs.reserve(n);
    for (int i = 0; i < n; ++i) {
        auto in  = bd / ("in_"  + std::to_string(i) + ".png");
        auto out = bd / ("out_" + std::to_string(i) + ".webp");
        write_png(in, 256, 256);
        pairs.emplace_back(in.string(), out.string());
    }

    for (auto _ : state) {
        auto r = convert_image_batch(pairs, "webp", false, std::nullopt, "crop");
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * n);
}
BENCHMARK(BM_ConvBatch)->Arg(4)->Arg(16)->Arg(64)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// Image merging benchmarks
// ---------------------------------------------------------------------------

struct MergeFix {
    fs::path tmp;
    std::vector<std::string> p4, p10, p25;
    std::string out;
    MergeFix() {
        tmp = fs::temp_directory_path() / "bm_merge";
        out = (tmp / "merged.png").string();
        p4  = make_png_batch(tmp / "4",  4,  256, 256);
        p10 = make_png_batch(tmp / "10", 10, 256, 256);
        p25 = make_png_batch(tmp / "25", 25, 256, 256);
    }
    ~MergeFix() { fs::remove_all(tmp); }
    const std::vector<std::string>& pick(int n) const {
        return n == 4 ? p4 : n == 10 ? p10 : p25;
    }
};
static MergeFix& mf() { static MergeFix f; return f; }

static void BM_MergeH(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    const auto& paths = mf().pick(n);
    for (auto _ : state)
        benchmark::DoNotOptimize(merge_images_horizontal(paths, mf().out, 0, "center"));
    state.SetItemsProcessed(state.iterations() * n);
}
BENCHMARK(BM_MergeH)->Arg(4)->Arg(10)->Arg(25)->Unit(benchmark::kMillisecond);

static void BM_MergeV(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));
    const auto& paths = mf().pick(n);
    for (auto _ : state)
        benchmark::DoNotOptimize(merge_images_vertical(paths, mf().out, 0, "center"));
    state.SetItemsProcessed(state.iterations() * n);
}
BENCHMARK(BM_MergeV)->Arg(4)->Arg(10)->Arg(25)->Unit(benchmark::kMillisecond);

static void BM_MergeGrid(benchmark::State& state) {
    const int n    = static_cast<int>(state.range(0));
    const auto& paths = mf().pick(n);
    auto side = static_cast<uint32_t>(std::ceil(std::sqrt(n)));
    for (auto _ : state)
        benchmark::DoNotOptimize(merge_images_grid(paths, mf().out, side, side, 0));
    state.SetItemsProcessed(state.iterations() * n);
}
BENCHMARK(BM_MergeGrid)->Arg(4)->Arg(10)->Arg(25)->Unit(benchmark::kMillisecond);

static void BM_MergeHSpacing(benchmark::State& state) {
    const uint32_t sp = static_cast<uint32_t>(state.range(0));
    for (auto _ : state)
        benchmark::DoNotOptimize(merge_images_horizontal(mf().p10, mf().out, sp, "center"));
}
BENCHMARK(BM_MergeHSpacing)->Arg(0)->Arg(10)->Arg(50)->Unit(benchmark::kMillisecond);
