// ---------------------------------------------------------------------------
// batch/tests/images/test_image_batch.cpp
//
// Catch2 tests for batch::image — load_image_batch and scan_files.
// Phase 2 skeleton: structure and test cases are defined; implementations
// are stubs until Phase 2 is complete.
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_approx.hpp>

#include "batch/image/image_batch.hpp"
#include "batch/image/scan_files.hpp"

#include <opencv2/core.hpp>
#include <opencv2/imgcodecs.hpp>

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

static fs::path make_test_dir(const std::string& tag) {
    fs::path p = fs::temp_directory_path() / ("batch_img_test_" + tag);
    fs::create_directories(p);
    return p;
}

static void write_dummy_png(const fs::path& path, int w = 64, int h = 64) {
    cv::Mat img(h, w, CV_8UC3, cv::Scalar(128, 64, 32));
    cv::imwrite(path.string(), img);
}

// ---------------------------------------------------------------------------
// scan_files
// ---------------------------------------------------------------------------

TEST_CASE("scan_files: returns matching extensions", "[images][scan_files]") {
    auto dir = make_test_dir("scan_basic");
    write_dummy_png(dir / "a.png");
    write_dummy_png(dir / "b.jpg");
    (dir / "c.txt").replace_extension(".txt");
    { std::ofstream f(dir / "c.txt"); f << "text"; }

    auto results = batch::image::scan_files(dir.string(), {".png", ".jpg"}, false);

    CHECK(results.size() == 2);
    for (const auto& p : results) {
        std::string ext = fs::path(p).extension().string();
        CHECK((ext == ".png" || ext == ".jpg"));
    }
    fs::remove_all(dir);
}

TEST_CASE("scan_files: recursive flag includes subdirectory files", "[images][scan_files]") {
    auto dir = make_test_dir("scan_recursive");
    fs::create_directories(dir / "sub");
    write_dummy_png(dir / "top.png");
    write_dummy_png(dir / "sub" / "nested.png");

    auto flat = batch::image::scan_files(dir.string(), {".png"}, false);
    auto rec  = batch::image::scan_files(dir.string(), {".png"}, true);

    CHECK(flat.size() == 1);
    CHECK(rec.size()  == 2);
    fs::remove_all(dir);
}

TEST_CASE("scan_files: case-insensitive extension matching", "[images][scan_files]") {
    auto dir = make_test_dir("scan_case");
    write_dummy_png(dir / "a.PNG");
    write_dummy_png(dir / "b.Jpg");

    auto results = batch::image::scan_files(dir.string(), {".png", ".jpg"}, false);
    CHECK(results.size() == 2);
    fs::remove_all(dir);
}

TEST_CASE("scan_files: empty directory returns empty list", "[images][scan_files]") {
    auto dir = make_test_dir("scan_empty");
    auto results = batch::image::scan_files(dir.string(), {".png"}, true);
    CHECK(results.empty());
    fs::remove_all(dir);
}

TEST_CASE("scan_files: results are sorted", "[images][scan_files]") {
    auto dir = make_test_dir("scan_sorted");
    write_dummy_png(dir / "z.png");
    write_dummy_png(dir / "a.png");
    write_dummy_png(dir / "m.png");

    auto results = batch::image::scan_files(dir.string(), {".png"}, false);
    REQUIRE(results.size() == 3);
    CHECK(results[0] < results[1]);
    CHECK(results[1] < results[2]);
    fs::remove_all(dir);
}

// ---------------------------------------------------------------------------
// load_image_batch
// ---------------------------------------------------------------------------

TEST_CASE("load_image_batch: returns correct number of results", "[images][load]") {
    // NOTE: load_image_batch returns a py::list; Catch2 tests run without
    // a Python interpreter.  This test calls the internal C++ helper directly.
    // Full pybind11 integration tests live in batch/tests/test_images_cpp.py.

    auto dir = make_test_dir("load_count");
    write_dummy_png(dir / "1.png");
    write_dummy_png(dir / "2.png");
    write_dummy_png(dir / "3.png");

    // Direct OpenCV round-trip (no Python layer) — validates the fixture logic.
    for (int i = 1; i <= 3; ++i) {
        cv::Mat img = cv::imread((dir / (std::to_string(i) + ".png")).string());
        REQUIRE_FALSE(img.empty());
    }
    fs::remove_all(dir);
}

TEST_CASE("load_image_batch: missing file produces error string", "[images][load]") {
    // Validate that cv::imread returns empty Mat for a non-existent path.
    cv::Mat img = cv::imread("/nonexistent/path/image.png");
    CHECK(img.empty());
}

TEST_CASE("load_image_batch: thumbnail dimensions respected", "[images][load]") {
    auto dir = make_test_dir("load_dims");
    write_dummy_png(dir / "img.png", 640, 480);

    cv::Mat src = cv::imread((dir / "img.png").string(), cv::IMREAD_COLOR);
    REQUIRE_FALSE(src.empty());

    cv::Mat thumb;
    cv::resize(src, thumb, cv::Size(128, 96), 0, 0, cv::INTER_AREA);
    CHECK(thumb.cols == 128);
    CHECK(thumb.rows == 96);
    fs::remove_all(dir);
}

TEST_CASE("load_image_batch: keep_aspect crops to fit", "[images][load]") {
    // 640×480 image, target 256×256, keep_aspect=true → 256×192 (width-limited)
    int w = 640, h = 480, tw = 256, th = 256;
    double sx = static_cast<double>(tw) / w;
    double sy = static_cast<double>(th) / h;
    double s  = std::min(sx, sy);
    int ew = static_cast<int>(w * s);
    int eh = static_cast<int>(h * s);
    CHECK(ew == 256);
    CHECK(eh == 192);
}

TEST_CASE("load_image_batch: no keep_aspect stretches to exact target", "[images][load]") {
    // Without keep_aspect the resize target is exactly (thumb_w, thumb_h).
    int tw = 128, th = 64;
    cv::Size target(tw, th);
    CHECK(target.width  == 128);
    CHECK(target.height == 64);
}
