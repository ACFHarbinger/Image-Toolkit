use fast_image_resize as fr;
use image::{DynamicImage, ImageFormat, ImageReader};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rayon::prelude::*;
use std::fs;

// Helper function to load image
fn load_image(path: &str) -> PyResult<DynamicImage> {
    ImageReader::open(path)
        .map_err(|e| PyValueError::new_err(format!("Failed to open file: {}", e)))?
        .decode()
        .map_err(|e| PyValueError::new_err(format!("Failed to decode image: {}", e)))
}

// Helper to save image
fn save_image(img: &DynamicImage, output_path: &str, format: &str) -> PyResult<()> {
    let fmt = match format.to_lowercase().as_str() {
        "png" => ImageFormat::Png,
        "jpg" | "jpeg" => ImageFormat::Jpeg,
        "webp" => ImageFormat::WebP,
        "bmp" => ImageFormat::Bmp,
        "ico" => ImageFormat::Ico,
        "tiff" => ImageFormat::Tiff,
        _ => {
            return Err(PyValueError::new_err(format!(
                "Unsupported format: {}",
                format
            )));
        }
    };

    img.save_with_format(output_path, fmt)
        .map_err(|e| PyValueError::new_err(format!("Failed to save image: {}", e)))
}

fn resize_image(img: &DynamicImage, new_w: u32, new_h: u32) -> PyResult<DynamicImage> {
    let width = img.width();
    let height = img.height();

    // Convert to RGBA8 for resizing
    let src_image = fr::images::Image::from_vec_u8(
        width,
        height,
        img.to_rgba8().into_raw(),
        fr::PixelType::U8x4,
    )
    .map_err(|e| {
        PyValueError::new_err(format!("Failed to create source image container: {}", e))
    })?;

    let mut dst_image = fr::images::Image::new(new_w, new_h, fr::PixelType::U8x4);
    let mut resizer = fr::Resizer::new();

    resizer
        .resize(&src_image, &mut dst_image, None)
        .map_err(|e| PyValueError::new_err(format!("Failed to resize: {}", e)))?;

    // Convert back to DynamicImage
    let buffer = dst_image.into_vec();
    Ok(DynamicImage::ImageRgba8(
        image::RgbaImage::from_raw(new_w, new_h, buffer).unwrap(),
    ))
}

fn crop_center(img: &DynamicImage, target_ratio: f32) -> PyResult<DynamicImage> {
    let w = img.width();
    let h = img.height();
    let current_ratio = w as f32 / h as f32;

    let (new_w, new_h) = if current_ratio > target_ratio {
        // Too wide, crop width
        let calc_w = (h as f32 * target_ratio) as u32;
        (calc_w, h)
    } else {
        // Too tall, crop height
        let calc_h = (w as f32 / target_ratio) as u32;
        (w, calc_h)
    };

    let x = (w - new_w) / 2;
    let y = (h - new_h) / 2;

    Ok(img.crop_imm(x, y, new_w, new_h))
}

fn pad_image(img: &DynamicImage, target_ratio: f32) -> PyResult<DynamicImage> {
    let w = img.width();
    let h = img.height();
    let current_ratio = w as f32 / h as f32;

    let (new_w, new_h) = if current_ratio > target_ratio {
        // Wider than target: Add height (Letterbox)
        let calc_h = (w as f32 / target_ratio) as u32;
        (w, calc_h)
    } else {
        // Taller than target: Add width (Pillarbox)
        let calc_w = (h as f32 * target_ratio) as u32;
        (calc_w, h)
    };

    let mut new_img = image::RgbaImage::new(new_w, new_h);
    // Fill with black/transparent (0,0,0,0) is default for new RgbaImage

    let x = (new_w - w) / 2;
    let y = (new_h - h) / 2;

    image::imageops::overlay(&mut new_img, img, x as i64, y as i64);
    Ok(DynamicImage::ImageRgba8(new_img))
}

fn stretch_image(img: &DynamicImage, target_ratio: f32) -> PyResult<DynamicImage> {
    let w = img.width();
    let h = img.height();
    let current_ratio = w as f32 / h as f32;

    let (new_w, new_h) = if current_ratio > target_ratio {
        // Current is wider than target.
        let calc_h = (w as f32 / target_ratio) as u32;
        (w, calc_h)
    } else {
        // Current is taller. Grow Width.
        let calc_w = (h as f32 * target_ratio) as u32;
        (calc_w, h)
    };

    // Stretch using fast_image_resize
    resize_image(img, new_w, new_h)
}

fn apply_ar_transform(
    img: &DynamicImage,
    ratio: Option<f32>,
    mode: &str,
) -> PyResult<DynamicImage> {
    if let Some(r) = ratio {
        match mode {
            "pad" => pad_image(img, r),
            "stretch" => stretch_image(img, r),
            _ => crop_center(img, r), // default to crop
        }
    } else {
        Ok(img.clone())
    }
}

#[pyfunction]
#[pyo3(signature = (input_path, output_path, output_format, delete_original, aspect_ratio=None, ar_mode=None))]
pub fn convert_single_image(
    input_path: String,
    output_path: String,
    output_format: String,
    delete_original: bool,
    aspect_ratio: Option<f32>,
    ar_mode: Option<String>,
) -> PyResult<bool> {
    let mode = ar_mode.unwrap_or_else(|| "crop".to_string());

    let img = load_image(&input_path)?;
    let processed_img = apply_ar_transform(&img, aspect_ratio, &mode)?;

    save_image(&processed_img, &output_path, &output_format)?;

    if delete_original {
        let _ = fs::remove_file(input_path);
    }

    Ok(true)
}

#[pyfunction]
#[pyo3(signature = (image_pairs, output_format, delete_original, aspect_ratio=None, ar_mode=None))]
pub fn convert_image_batch(
    py: Python,
    image_pairs: Vec<(String, String)>, // (input_path, output_path)
    output_format: String,
    delete_original: bool,
    aspect_ratio: Option<f32>,
    ar_mode: Option<String>,
) -> PyResult<Vec<String>> {
    let mode = ar_mode.unwrap_or_else(|| "crop".to_string());

    let results: Vec<Option<String>> = py.detach(|| {
        image_pairs
            .par_iter()
            .map(|(path, out_path)| match load_image(path) {
                Ok(img) => match apply_ar_transform(&img, aspect_ratio, &mode) {
                    Ok(proc_img) => match save_image(&proc_img, &out_path, &output_format) {
                        Ok(_) => {
                            if delete_original {
                                let _ = fs::remove_file(path);
                            }
                            Some(out_path.clone())
                        }
                        Err(_) => None,
                    },
                    Err(_) => None,
                },
                Err(_) => None,
            })
            .collect()
    });

    Ok(results.into_iter().flatten().collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{Rgb, RgbImage};
    use tempfile::tempdir;

    fn create_test_image(path: &str, w: u32, h: u32) {
        let mut img = RgbImage::new(w, h);
        for x in 0..w {
            for y in 0..h {
                img.put_pixel(x, y, Rgb([255, 0, 0]));
            }
        }
        img.save(path).unwrap();
    }

    #[test]
    fn test_crop() {
        let dir = tempdir().unwrap();
        let in_path = dir.path().join("in.png");
        let out_path = dir.path().join("out.png");

        // 200x100 (2:1)
        create_test_image(in_path.to_str().unwrap(), 200, 100);

        // Target 1:1 (Square) - Should crop to 100x100
        convert_single_image(
            in_path.to_str().unwrap().to_string(),
            out_path.to_str().unwrap().to_string(),
            "png".to_string(),
            false,
            Some(1.0),
            Some("crop".to_string()),
        )
        .unwrap();

        let res = image::open(&out_path).unwrap();
        assert_eq!(res.width(), 100);
        assert_eq!(res.height(), 100);
    }

    #[test]
    fn test_pad() {
        let dir = tempdir().unwrap();
        let in_path = dir.path().join("in_pad.png");
        let out_path = dir.path().join("out_pad.png");

        // 200x100 (2:1)
        create_test_image(in_path.to_str().unwrap(), 200, 100);

        // Target 1:1 (Square) - Should pad to 200x200
        convert_single_image(
            in_path.to_str().unwrap().to_string(),
            out_path.to_str().unwrap().to_string(),
            "png".to_string(),
            false,
            Some(1.0),
            Some("pad".to_string()),
        )
        .unwrap();

        let res = image::open(&out_path).unwrap();
        assert_eq!(res.width(), 200);
        assert_eq!(res.height(), 200);
    }

    #[test]
    fn test_stretch() {
        let dir = tempdir().unwrap();
        let in_path = dir.path().join("in_str.png");
        let out_path = dir.path().join("out_str.png");

        // 100x100 (1:1)
        create_test_image(in_path.to_str().unwrap(), 100, 100);

        // Target 2:1 -> Should stretch width to 200 or height?
        // Logic: if current ratio (1.0) < target (2.0) -> current taller. Grow Width?
        // Yes, make it 200x100.

        convert_single_image(
            in_path.to_str().unwrap().to_string(),
            out_path.to_str().unwrap().to_string(),
            "png".to_string(),
            false,
            Some(2.0),
            Some("stretch".to_string()),
        )
        .unwrap();

        let res = image::open(&out_path).unwrap();
        assert_eq!(res.width(), 200);
        assert_eq!(res.height(), 100);
    }

    #[test]
    fn test_convert_batch() {
        let dir = tempdir().unwrap();
        let p1 = dir.path().join("1.png");
        let p2 = dir.path().join("2.png");
        let o1 = dir.path().join("out1.png");
        let o2 = dir.path().join("out2.png");

        create_test_image(p1.to_str().unwrap(), 50, 50);
        create_test_image(p2.to_str().unwrap(), 50, 50);

        Python::initialize();
        Python::attach(|py| {
            let pairs = vec![
                (
                    p1.to_str().unwrap().to_string(),
                    o1.to_str().unwrap().to_string(),
                ),
                (
                    p2.to_str().unwrap().to_string(),
                    o2.to_str().unwrap().to_string(),
                ),
            ];

            let res = convert_image_batch(py, pairs, "png".to_string(), false, None, None).unwrap();

            assert_eq!(res.len(), 2);
            assert!(o1.exists());
            assert!(o2.exists());
        });
    }
}
