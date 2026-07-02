// ---------------------------------------------------------------------------
// base/benchmarks/bench_image.cpp
//
// Google Benchmark suite for base::image — the OpenMP-parallel image batch
// loader and filesystem scanner:
//   • load_image_batch: single / small batch / large batch at 256px thumbnails
//   • load_image_batch: 1080p sources (decoder + INTER_AREA resize bottleneck)
//   • load_image_batch: keep_aspect=true vs false (geometry branch)
//   • scan_files: flat, recursive, multi-directory root, multi-extension filter
//   • scan_files_multi: scanning multiple root directories at once
//
// Mirrors the Python benchmarks in backend/benchmark/bench_cpp_image_processing.py
// and bench_thumbnails.py, but runs at the pure C++ layer without Python overhead.
//
// Build:   cmake --build build/base --target base_bench_image
// Run:     ./build/base/benchmarks/base_bench_image --benchmark_format=json
// ---------------------------------------------------------------------------

// BATCH_TESTS suppresses the pybind11 embed guard in common.hpp
#define BATCH_TESTS 1

#include <benchmark/benchmark.h>

#include "image/image_batch.hpp"
#include "image/scan_files.hpp"

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>

namespace fs = std::filesystem;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

namespace {

void write_png(const fs::path& p, int w, int h) {
    cv::Mat img(h, w, CV_8UC3, cv::Scalar(128, 64, 192));
    cv::imwrite(p.string(), img);
}

std::vector<std::string> make_png_dir(const fs::path& dir, int count,
                                       int w, int h) {
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

} // namespace

// ---------------------------------------------------------------------------
// load_image_batch — thumbnail size 256×256
// ---------------------------------------------------------------------------

struct ImageBatchFix {
    fs::path tmp;
    // 512×512 images
    std::vector<std::string> p512_1;
    std::vector<std::string> p512_8;
    std::vector<std::string> p512_32;
    // 1920×1080 images
    std::vector<std::string> p1080_1;
    std::vector<std::string> p1080_8;

    ImageBatchFix() {
        tmp = fs::temp_directory_path() / "bm_image_batch";
        p512_1  = make_png_dir(tmp / "512_1",  1,  512,  512);
        p512_8  = make_png_dir(tmp / "512_8",  8,  512,  512);
        p512_32 = make_png_dir(tmp / "512_32", 32, 512,  512);
        p1080_1 = make_png_dir(tmp / "1080_1", 1, 1920, 1080);
        p1080_8 = make_png_dir(tmp / "1080_8", 8, 1920, 1080);
    }
    ~ImageBatchFix() { fs::remove_all(tmp); }
};

static ImageBatchFix& ibf() { static ImageBatchFix f; return f; }

// Single image (no parallelism, measures raw imread + resize cost)
static void BM_LoadBatch_512_Single(benchmark::State& state) {
    auto& f = ibf();
    for (auto _ : state) {
        auto r = base::image::load_image_batch(f.p512_1, 256, 256, true);
        benchmark::DoNotOptimize(r);
    }
}
BENCHMARK(BM_LoadBatch_512_Single)->Unit(benchmark::kMillisecond);

// 8 images — light parallelism (typically fits in one OMP team)
static void BM_LoadBatch_512_8(benchmark::State& state) {
    auto& f = ibf();
    for (auto _ : state) {
        auto r = base::image::load_image_batch(f.p512_8, 256, 256, true);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * 8);
}
BENCHMARK(BM_LoadBatch_512_8)->Unit(benchmark::kMillisecond);

// 32 images — saturates available OMP threads on most CPUs
static void BM_LoadBatch_512_32(benchmark::State& state) {
    auto& f = ibf();
    for (auto _ : state) {
        auto r = base::image::load_image_batch(f.p512_32, 256, 256, true);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * 32);
}
BENCHMARK(BM_LoadBatch_512_32)->Unit(benchmark::kMillisecond);

// 1080p source — decoder + INTER_AREA downscale are the bottleneck
static void BM_LoadBatch_1080p_Single(benchmark::State& state) {
    auto& f = ibf();
    for (auto _ : state) {
        auto r = base::image::load_image_batch(f.p1080_1, 256, 256, true);
        benchmark::DoNotOptimize(r);
    }
}
BENCHMARK(BM_LoadBatch_1080p_Single)->Unit(benchmark::kMillisecond);

static void BM_LoadBatch_1080p_8(benchmark::State& state) {
    auto& f = ibf();
    for (auto _ : state) {
        auto r = base::image::load_image_batch(f.p1080_8, 256, 256, true);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * 8);
}
BENCHMARK(BM_LoadBatch_1080p_8)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// keep_aspect true vs false (geometry branch cost)
// ---------------------------------------------------------------------------

static void BM_LoadBatch_KeepAspect_True(benchmark::State& state) {
    auto& f = ibf();
    for (auto _ : state)
        benchmark::DoNotOptimize(base::image::load_image_batch(f.p512_8, 256, 256, true));
    state.SetItemsProcessed(state.iterations() * 8);
}
BENCHMARK(BM_LoadBatch_KeepAspect_True)->Unit(benchmark::kMillisecond);

static void BM_LoadBatch_KeepAspect_False(benchmark::State& state) {
    auto& f = ibf();
    for (auto _ : state)
        benchmark::DoNotOptimize(base::image::load_image_batch(f.p512_8, 256, 256, false));
    state.SetItemsProcessed(state.iterations() * 8);
}
BENCHMARK(BM_LoadBatch_KeepAspect_False)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// Thumbnail size sensitivity (same 8× 512px batch, varying output dim)
// ---------------------------------------------------------------------------

static void BM_LoadBatch_ThumbSize(benchmark::State& state) {
    auto& f = ibf();
    const int thumb = static_cast<int>(state.range(0));
    for (auto _ : state)
        benchmark::DoNotOptimize(base::image::load_image_batch(f.p512_8, thumb, thumb, true));
    state.SetItemsProcessed(state.iterations() * 8);
}
BENCHMARK(BM_LoadBatch_ThumbSize)->Arg(64)->Arg(180)->Arg(256)->Arg(512)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// scan_files — base::image::scan_files
// ---------------------------------------------------------------------------

struct ScanFix {
    fs::path root;
    // Flat directory with various counts
    fs::path flat_200;
    // Recursive tree: 4 subdirs × 50 files = 200 total
    fs::path rec_200;
    // Mixed extension directory
    fs::path mixed;

    ScanFix() {
        root     = fs::temp_directory_path() / "bm_scan_files";
        flat_200 = root / "flat_200";
        rec_200  = root / "rec_200";
        mixed    = root / "mixed";

        // Flat 200 PNGs
        fs::create_directories(flat_200);
        for (int i = 0; i < 200; ++i)
            std::ofstream(flat_200 / ("f_" + std::to_string(i) + ".png")).put('\0');

        // Recursive: 4 subdirs
        for (int d = 0; d < 4; ++d) {
            auto sub = rec_200 / ("d" + std::to_string(d));
            fs::create_directories(sub);
            for (int i = 0; i < 50; ++i)
                std::ofstream(sub / ("f_" + std::to_string(i) + ".jpg")).put('\0');
        }

        // Mixed extensions
        fs::create_directories(mixed);
        for (int i = 0; i < 100; ++i) {
            std::ofstream(mixed / ("a_" + std::to_string(i) + ".png")).put('\0');
            std::ofstream(mixed / ("b_" + std::to_string(i) + ".jpg")).put('\0');
            std::ofstream(mixed / ("c_" + std::to_string(i) + ".txt")).put('\0');
        }
    }
    ~ScanFix() { fs::remove_all(root); }
};

static ScanFix& sf() { static ScanFix f; return f; }

static void BM_ScanFlat200(benchmark::State& state) {
    auto& f = sf();
    for (auto _ : state) {
        auto r = base::image::scan_files(f.flat_200.string(), {".png"}, false);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * 200);
}
BENCHMARK(BM_ScanFlat200)->Unit(benchmark::kMicrosecond);

static void BM_ScanRecursive200(benchmark::State& state) {
    auto& f = sf();
    for (auto _ : state) {
        auto r = base::image::scan_files(f.rec_200.string(), {".jpg"}, true);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * 200);
}
BENCHMARK(BM_ScanRecursive200)->Unit(benchmark::kMicrosecond);

// Multi-extension filter (PNG + JPG, skipping TXT)
static void BM_ScanMultiExt(benchmark::State& state) {
    auto& f = sf();
    for (auto _ : state) {
        auto r = base::image::scan_files(f.mixed.string(), {".png", ".jpg"}, false);
        benchmark::DoNotOptimize(r);
    }
    state.SetItemsProcessed(state.iterations() * 200); // 100 PNG + 100 JPG
}
BENCHMARK(BM_ScanMultiExt)->Unit(benchmark::kMicrosecond);

// scan_files_multi: combine two root directories
static void BM_ScanMultiRoot(benchmark::State& state) {
    auto& f = sf();
    std::vector<std::string> roots = {f.flat_200.string(), f.rec_200.string()};
    for (auto _ : state) {
        auto r = base::image::scan_files_multi(roots, {".png", ".jpg"}, true);
        benchmark::DoNotOptimize(r);
    }
}
BENCHMARK(BM_ScanMultiRoot)->Unit(benchmark::kMicrosecond);
