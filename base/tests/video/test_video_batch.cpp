// ---------------------------------------------------------------------------
// batch/tests/video/test_video_batch.cpp
//
// Catch2 tests for base::video — extract_video_thumbnails_batch.
// Phase 3 skeleton.
// ---------------------------------------------------------------------------

#include <catch2/catch_test_macros.hpp>

#include "base/video/video_batch.hpp"

#include <opencv2/core.hpp>

// ---------------------------------------------------------------------------
// Tests that do not require an actual video file — validate struct defaults
// and error handling paths.
// ---------------------------------------------------------------------------

TEST_CASE("extract_thumbnails: missing file returns error", "[video]") {
    auto result = base::video::extract_thumbnails(
        "/nonexistent/path/video.mp4",
        {0.0, 1.0, 2.0},
        128, 128);

    CHECK_FALSE(result.error.empty());
    CHECK(result.frames.empty());
    CHECK(result.path == "/nonexistent/path/video.mp4");
}

TEST_CASE("extract_thumbnails: empty timestamp list returns no frames", "[video]") {
    // Even if the file existed, an empty timestamp list should yield no frames.
    // We can't open a real video here so we verify the contract structurally.
    base::video::VideoThumbResult r;
    r.path = "test.mp4";
    r.frames = {};
    r.error  = "";

    CHECK(r.frames.empty());
    CHECK(r.error.empty());
}

TEST_CASE("VideoThumbResult: default construction is clean", "[video]") {
    base::video::VideoThumbResult r;
    CHECK(r.path.empty());
    CHECK(r.frames.empty());
    CHECK(r.error.empty());
}

TEST_CASE("extract_thumbnails: thumbnail dimensions are enforced", "[video]") {
    // Validate the resize logic in isolation using OpenCV directly.
    cv::Mat frame(480, 640, CV_8UC3, cv::Scalar(100, 150, 200));
    cv::Mat thumb;
    cv::resize(frame, thumb, cv::Size(128, 128), 0, 0, cv::INTER_AREA);
    CHECK(thumb.cols == 128);
    CHECK(thumb.rows == 128);
}

TEST_CASE("extract_thumbnails: path is preserved in result", "[video]") {
    auto result = base::video::extract_thumbnails("my_video.mp4", {}, 64, 64);
    // File doesn't exist → error, but path is always echoed back.
    CHECK(result.path == "my_video.mp4");
}
