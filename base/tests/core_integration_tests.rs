use base::core::file_system::*;
use base::core::image_converter::*;
use base::core::image_finder::*;
use base::core::image_merger::*;
use image::{Rgb, RgbImage};
use pyo3::Python;
use tempfile::tempdir;

#[test]
fn test_full_workflow_integration() {
    Python::initialize();
    Python::attach(|py| {
        let dir = tempdir().unwrap();
        let dir_path = dir.path().to_str().unwrap().to_string();

        // 1. Create test images
        let p1 = dir.path().join("img1.png");
        let p2 = dir.path().join("img2.png");
        let p3 = dir.path().join("img1_dup.png");

        let mut img1 = RgbImage::new(100, 100);
        for x in 0..100 {
            for y in 0..100 {
                img1.put_pixel(x, y, Rgb([255, 0, 0]));
            }
        }
        img1.save(&p1).unwrap();

        let mut img2 = RgbImage::new(100, 100);
        for x in 0..100 {
            for y in 0..100 {
                img2.put_pixel(x, y, Rgb([0, 255, 0]));
            }
        }
        img2.save(&p2).unwrap();

        // Copy p1 to p3
        std::fs::copy(&p1, &p3).unwrap();

        // 2. Test File System Scan
        let files = get_files_by_extension(py, dir_path.clone(), "png".to_string(), false).unwrap();
        assert_eq!(files.len(), 3);

        // 3. Test Duplicate Finder
        let dups =
            find_duplicate_images(py, dir_path.clone(), vec!["png".to_string()], false).unwrap();
        assert_eq!(dups.len(), 1);
        let dup_group = dups.values().next().unwrap();
        assert_eq!(dup_group.len(), 2);
        assert!(dup_group.iter().any(|s| s.contains("img1.png")));
        assert!(dup_group.iter().any(|s| s.contains("img1_dup.png")));

        // 4. Test Image Merger (Horizontal)
        let out_merge = dir.path().join("merged.png");
        let merge_paths = vec![
            p1.to_str().unwrap().to_string(),
            p2.to_str().unwrap().to_string(),
        ];
        let res_merge = merge_images_horizontal(
            merge_paths,
            out_merge.to_str().unwrap().to_string(),
            10,
            "center".to_string(),
        )
        .unwrap();
        assert!(res_merge);
        assert!(out_merge.exists());

        let merged_img = image::open(&out_merge).unwrap();
        assert_eq!(merged_img.width(), 100 + 100 + 10);
        assert_eq!(merged_img.height(), 100);

        // 5. Test Image Converter
        let out_converted = dir.path().join("converted.jpg");
        let res_conv = convert_single_image(
            out_merge.to_str().unwrap().to_string(),
            out_converted.to_str().unwrap().to_string(),
            "jpg".to_string(),
            false,
            Some(1.0), // Square
            Some("crop".to_string()),
        )
        .unwrap();
        assert!(res_conv);
        assert!(out_converted.exists());

        let conv_img = image::open(&out_converted).unwrap();
        assert_eq!(conv_img.width(), 100); // Cropped from 210x100 to 100x100
        assert_eq!(conv_img.height(), 100);

        // 6. Test Batch Delete
        let deleted =
            delete_files_by_extensions(py, dir_path.clone(), vec!["png".to_string()]).unwrap();
        assert_eq!(deleted, 4); // img1, img2, img1_dup, merged.png
                                // Actually it should delete 4 if merged exists.
                                // Let's check files again.
        let files_after =
            get_files_by_extension(py, dir_path.clone(), "png".to_string(), false).unwrap();
        assert_eq!(files_after.len(), 0);
    });
}
