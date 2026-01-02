use base::extract_video_thumbnails_batch;
use base::load_image_batch;
use base::scan_files;
use image::{Rgb, RgbImage};
use pyo3::Python;
use tempfile::tempdir;

#[test]
fn test_scan_files_integration() {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let dir = tempdir().unwrap();
        // Create a non-hidden subdirectory to scan
        let sub = dir.path().join("data");
        std::fs::create_dir(&sub).unwrap();

        let p1 = sub.join("a.txt");
        let p2 = sub.join("b.jpg");
        let p3 = sub.join("c.png");

        std::fs::write(&p1, "text").unwrap();
        std::fs::write(&p2, "jpeg").unwrap();
        std::fs::write(&p3, "png").unwrap();

        // 1. Scan for jpg
        let results = scan_files(
            py,
            vec![sub.to_str().unwrap().to_string()],
            vec!["jpg".to_string()],
            false,
        )
        .unwrap();
        assert_eq!(results.len(), 1, "Expected 1 jpg file");
        assert!(results[0].ends_with("b.jpg"));

        // 2. Scan for txt and png
        let results = scan_files(
            py,
            vec![sub.to_str().unwrap().to_string()],
            vec!["txt".to_string(), "png".to_string()],
            false,
        )
        .unwrap();
        assert_eq!(results.len(), 2, "Expected 2 files (txt, png)");
    });
}

#[test]
fn test_load_image_batch_integration() {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let dir = tempdir().unwrap();
        let p1 = dir.path().join("test.png");

        let mut img = RgbImage::new(100, 50); // 2:1 aspect
        for x in 0..100 {
            for y in 0..50 {
                img.put_pixel(x, y, Rgb([255, 0, 0]));
            }
        }
        img.save(&p1).unwrap();

        // Load with target size 20
        // Aspect ratio 2:1. If width > height: (20, 20/2) = (20, 10)
        let paths = vec![p1.to_str().unwrap().to_string()];
        let results = load_image_batch(py, paths, 20).unwrap();

        assert_eq!(results.len(), 1);
        let (path, _bytes, w, h) = &results[0];
        assert_eq!(path, p1.to_str().unwrap());
        assert_eq!(*w, 20);
        assert_eq!(*h, 10);
    });
}

#[test]
fn test_extract_video_thumbnails_integration_failure() {
    // Tests that function runs but returns empty for non-video file (or handles ffmpeg fail)
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let dir = tempdir().unwrap();
        let p1 = dir.path().join("not_a_video.txt");
        std::fs::write(&p1, "dummy").unwrap();

        let paths = vec![p1.to_str().unwrap().to_string()];
        let results = extract_video_thumbnails_batch(py, paths, 100).unwrap();

        // Should be empty list because ffmpeg failed to extract or decode
        assert!(results.is_empty());
    });
}
