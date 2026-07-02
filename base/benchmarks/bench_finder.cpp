// ---------------------------------------------------------------------------
// base/benchmarks/bench_finder.cpp
//
// Google Benchmark suite for base::core::finder — duplicate and
// perceptual-hash image detection:
//
//   • sha256_file: single file hashing at different file sizes
//   • compute_phash: pHash (dct/mean) at different image resolutions
//   • find_duplicate_images: SHA-256 grouping over N image corpus
//   • find_similar_images_phash: O(n²) pHash + union-find grouping
//   • Hamming distance threshold sensitivity (pHash at threshold 0 vs 10)
//
// All images are written once as PNG fixtures and reused across iterations.
// The benchmarks are designed to expose the two main cost centres:
//   1. Parallel file I/O + SHA-256 / pHash computation (OpenMP).
//   2. O(n²) Hamming pairwise grouping.
//
// Build:   cmake --build build/base --target base_bench_finder
// Run:     ./build/base/benchmarks/base_bench_finder --benchmark_format=json
// ---------------------------------------------------------------------------

#include <benchmark/benchmark.h>

#include "core/finder.hpp"

#include <filesystem>
#include <fstream>
#include <random>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>

namespace fs = std::filesystem;
using namespace base::core;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

namespace {

/// Write a unique solid-colour PNG (avoids SHA-256 collisions)
void write_unique_png(const fs::path& p, int w, int h, unsigned seed) {
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> dist(0, 255);
    cv::Vec3b c(dist(rng), dist(rng), dist(rng));
    cv::Mat img(h, w, CV_8UC3, cv::Scalar(c[0], c[1], c[2]));
    // Add a random pixel so images are truly unique byte-for-byte
    img.at<cv::Vec3b>(0, 0) = cv::Vec3b(seed & 0xFF, (seed >> 8) & 0xFF, (seed >> 16) & 0xFF);
    cv::imwrite(p.string(), img);
}

/// Write N images where the first M are duplicates of image 0
void write_corpus_with_dups(const fs::path& dir, int total, int dups,
                             int w = 128, int h = 128) {
    fs::create_directories(dir);
    // Write the "original" that will be duplicated
    auto orig = dir / "orig.png";
    write_unique_png(orig, w, h, 0);

    for (int i = 0; i < total; ++i) {
        auto p = dir / ("img_" + std::to_string(i) + ".png");
        if (i < dups) {
            // Copy the original to create true duplicates
            fs::copy_file(orig, p, fs::copy_options::overwrite_existing);
        } else {
            write_unique_png(p, w, h, static_cast<unsigned>(i + 1));
        }
    }
}

} // namespace

// ---------------------------------------------------------------------------
// sha256_file: cost of hashing a single file at different sizes
// ---------------------------------------------------------------------------

struct SHA256Fix {
    fs::path tmp;
    std::string file_small;  // ~1 KB
    std::string file_medium; // ~1 MB (PNG of 512×512)
    std::string file_large;  // ~3 MB (PNG of 1024×1024)

    SHA256Fix() {
        tmp = fs::temp_directory_path() / "bm_sha256";
        fs::create_directories(tmp);

        // Small: raw binary file
        auto ps = tmp / "small.bin";
        { std::ofstream f(ps, std::ios::binary); f << std::string(1024, 'A'); }
        file_small = ps.string();

        // Medium: PNG image
        auto pm = tmp / "medium.png";
        cv::Mat m(512, 512, CV_8UC3, cv::Scalar(100, 150, 200));
        cv::imwrite(pm.string(), m);
        file_medium = pm.string();

        // Large: PNG image
        auto pl = tmp / "large.png";
        cv::Mat l(1024, 1024, CV_8UC3, cv::Scalar(50, 80, 120));
        cv::imwrite(pl.string(), l);
        file_large = pl.string();
    }
    ~SHA256Fix() { fs::remove_all(tmp); }
};

static SHA256Fix& shf() { static SHA256Fix f; return f; }

static void BM_SHA256_SmallFile(benchmark::State& state) {
    auto& f = shf();
    for (auto _ : state)
        benchmark::DoNotOptimize(sha256_file(f.file_small));
}
BENCHMARK(BM_SHA256_SmallFile)->Unit(benchmark::kMicrosecond);

static void BM_SHA256_MediumFile(benchmark::State& state) {
    auto& f = shf();
    for (auto _ : state)
        benchmark::DoNotOptimize(sha256_file(f.file_medium));
}
BENCHMARK(BM_SHA256_MediumFile)->Unit(benchmark::kMillisecond);

static void BM_SHA256_LargeFile(benchmark::State& state) {
    auto& f = shf();
    for (auto _ : state)
        benchmark::DoNotOptimize(sha256_file(f.file_large));
}
BENCHMARK(BM_SHA256_LargeFile)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// compute_phash: cost at different source resolutions
// ---------------------------------------------------------------------------

struct PHashFix {
    fs::path tmp;
    std::string img_small;   // 64×64
    std::string img_medium;  // 512×512
    std::string img_large;   // 1920×1080

    PHashFix() {
        tmp = fs::temp_directory_path() / "bm_phash";
        fs::create_directories(tmp);

        auto write = [&](const char* name, int w, int h) {
            auto p = tmp / name;
            cv::Mat img(h, w, CV_8UC1);  // grayscale, random
            cv::randu(img, 0, 255);
            cv::imwrite(p.string(), img);
            return p.string();
        };

        img_small  = write("s.png",   64,   64);
        img_medium = write("m.png",  512,  512);
        img_large  = write("l.png", 1920, 1080);
    }
    ~PHashFix() { fs::remove_all(tmp); }
};

static PHashFix& phf() { static PHashFix f; return f; }

static void BM_PHash_Small(benchmark::State& state) {
    for (auto _ : state)
        benchmark::DoNotOptimize(compute_phash(phf().img_small));
}
BENCHMARK(BM_PHash_Small)->Unit(benchmark::kMicrosecond);

static void BM_PHash_Medium(benchmark::State& state) {
    for (auto _ : state)
        benchmark::DoNotOptimize(compute_phash(phf().img_medium));
}
BENCHMARK(BM_PHash_Medium)->Unit(benchmark::kMicrosecond);

static void BM_PHash_Large(benchmark::State& state) {
    for (auto _ : state)
        benchmark::DoNotOptimize(compute_phash(phf().img_large));
}
BENCHMARK(BM_PHash_Large)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// find_duplicate_images: SHA-256 grouping over a corpus of N images.
// Parameterised by total image count and duplicate fraction.
// ---------------------------------------------------------------------------

static void BM_FindDuplicates(benchmark::State& state) {
    const int n    = static_cast<int>(state.range(0));
    const int dups = n / 4;  // 25% duplicates

    fs::path dir = fs::temp_directory_path() / ("bm_dup_" + std::to_string(n));
    fs::remove_all(dir);
    write_corpus_with_dups(dir, n, dups, 128, 128);

    for (auto _ : state) {
        auto res = find_duplicate_images(dir.string(), {".png"}, true);
        benchmark::DoNotOptimize(res);
    }
    state.SetItemsProcessed(state.iterations() * n);
    fs::remove_all(dir);
}
BENCHMARK(BM_FindDuplicates)->Arg(20)->Arg(50)->Arg(100)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// find_similar_images_phash: O(n²) pHash + union-find grouping.
// Parameterised by corpus size; threshold fixed at 5 (default).
// ---------------------------------------------------------------------------

static void BM_FindSimilarPhash(benchmark::State& state) {
    const int n = static_cast<int>(state.range(0));

    fs::path dir = fs::temp_directory_path() / ("bm_phash_sim_" + std::to_string(n));
    fs::remove_all(dir);

    // All images distinct (worst case for union-find: no merges)
    fs::create_directories(dir);
    for (int i = 0; i < n; ++i)
        write_unique_png(dir / ("img_" + std::to_string(i) + ".png"), 128, 128,
                         static_cast<unsigned>(i + 100));

    for (auto _ : state) {
        auto res = find_similar_images_phash(dir.string(), {".png"}, /*threshold=*/5);
        benchmark::DoNotOptimize(res);
    }
    // The inner loop is O(n²) comparisons
    state.SetItemsProcessed(state.iterations() * static_cast<int64_t>(n) * (n - 1) / 2);
    fs::remove_all(dir);
}
BENCHMARK(BM_FindSimilarPhash)->Arg(20)->Arg(50)->Arg(100)->Unit(benchmark::kMillisecond);

// ---------------------------------------------------------------------------
// Threshold sensitivity: pHash grouping at threshold 0 (exact) vs 10 (loose)
// ---------------------------------------------------------------------------

static void BM_PhashThreshold(benchmark::State& state) {
    const uint32_t threshold = static_cast<uint32_t>(state.range(0));
    const int n = 40;

    fs::path dir = fs::temp_directory_path() / ("bm_phash_thresh_" + std::to_string(threshold));
    fs::remove_all(dir);
    fs::create_directories(dir);
    for (int i = 0; i < n; ++i)
        write_unique_png(dir / ("img_" + std::to_string(i) + ".png"), 128, 128,
                         static_cast<unsigned>(i + 200));

    for (auto _ : state) {
        auto res = find_similar_images_phash(dir.string(), {".png"}, threshold);
        benchmark::DoNotOptimize(res);
    }
    fs::remove_all(dir);
}
BENCHMARK(BM_PhashThreshold)->Arg(0)->Arg(5)->Arg(10)->Unit(benchmark::kMillisecond);
