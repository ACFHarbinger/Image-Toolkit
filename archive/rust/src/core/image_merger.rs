use anyhow::{anyhow, Result};
use fast_image_resize as fr;
use image::{DynamicImage, ImageReader, RgbaImage};
#[cfg(feature = "python")]
use pyo3::exceptions::PyValueError;
#[cfg(feature = "python")]
use pyo3::prelude::*;

// §2.12 — Two-pass streaming merger: Pass 1 reads only image headers (width/height)
// via image::image_dimensions() so canvas dimensions can be computed without loading
// any pixel data.  Pass 2 loads and blits one image at a time, dropping each
// DynamicImage immediately after the overlay.  Peak RAM = 1 image + output canvas,
// instead of N images + output canvas.

fn load_img(path: &str) -> Result<DynamicImage> {
    ImageReader::open(path)
        .map_err(|e| anyhow!("Failed to open: {}", e))?
        .decode()
        .map_err(|e| anyhow!("Failed to decode: {}", e))
}

/// Pass-1 helper: read (width, height) from the image header only (no pixel decode).
fn read_dimensions(path: &str) -> Result<(u32, u32)> {
    image::image_dimensions(path).map_err(|e| anyhow!("Failed to read dimensions of {}: {}", path, e))
}

fn fast_resize(img: DynamicImage, w: u32, h: u32) -> DynamicImage {
    let src_w = img.width();
    let src_h = img.height();
    if src_w == w && src_h == h {
        return img;
    }

    let src_image = fr::images::Image::from_vec_u8(
        src_w,
        src_h,
        img.to_rgba8().into_raw(),
        fr::PixelType::U8x4,
    )
    .unwrap();

    let mut dst_image = fr::images::Image::new(w, h, fr::PixelType::U8x4);
    let mut resizer = fr::Resizer::new();
    resizer.resize(&src_image, &mut dst_image, None).unwrap();

    DynamicImage::ImageRgba8(RgbaImage::from_raw(w, h, dst_image.into_vec()).unwrap())
}

pub fn merge_images_horizontal_core(
    image_paths: &[String],
    output_path: &str,
    spacing: u32,
    align_mode: &str,
) -> Result<bool> {
    if image_paths.is_empty() {
        return Ok(false);
    }

    // Pass 1 — read headers only to compute canvas dimensions
    let dims: Vec<(u32, u32)> = image_paths
        .iter()
        .filter_map(|p| read_dimensions(p).ok())
        .collect();

    if dims.is_empty() {
        return Ok(false);
    }

    let max_h = dims.iter().map(|&(_, h)| h).max().unwrap();
    let total_width: u32 = dims.iter().map(|&(w, _)| w).sum::<u32>()
        + (spacing * (dims.len() as u32 - 1));

    let mut canvas = RgbaImage::new(total_width, max_h);
    for p in canvas.pixels_mut() {
        *p = image::Rgba([255, 255, 255, 255]);
    }

    // Pass 2 — load, blit, drop one image at a time
    let mut current_x: u32 = 0;
    let mut blitted = 0usize;

    for path in image_paths {
        let img = match load_img(path) {
            Ok(i) => i,
            Err(_) => continue,
        };

        let img = if align_mode == "stretch" || align_mode == "squish" {
            let w = img.width();
            fast_resize(img, w, max_h)
        } else {
            img
        };

        let (w, h) = (img.width(), img.height());
        let y_offset: u32 = match align_mode {
            "bottom" => max_h - h,
            "center" => (max_h - h) / 2,
            _ => 0,
        };

        image::imageops::overlay(&mut canvas, &img, current_x as i64, y_offset as i64);
        current_x += w + spacing;
        blitted += 1;
        // img is dropped here, freeing its pixel buffer immediately
    }

    if blitted == 0 {
        return Ok(false);
    }

    canvas
        .save(output_path)
        .map_err(|e| anyhow!("Failed to save: {}", e))?;
    Ok(true)
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn merge_images_horizontal(
    image_paths: Vec<String>,
    output_path: String,
    spacing: u32,
    align_mode: String,
) -> PyResult<bool> {
    merge_images_horizontal_core(&image_paths, &output_path, spacing, &align_mode)
        .map_err(|e| PyValueError::new_err(format!("{}", e)))
}

pub fn merge_images_vertical_core(
    image_paths: &[String],
    output_path: &str,
    spacing: u32,
    align_mode: &str,
) -> Result<bool> {
    if image_paths.is_empty() {
        return Ok(false);
    }

    // Pass 1 — read headers only
    let dims: Vec<(u32, u32)> = image_paths
        .iter()
        .filter_map(|p| read_dimensions(p).ok())
        .collect();

    if dims.is_empty() {
        return Ok(false);
    }

    let max_w = dims.iter().map(|&(w, _)| w).max().unwrap();
    let total_height: u32 = dims.iter().map(|&(_, h)| h).sum::<u32>()
        + (spacing * (dims.len() as u32 - 1));

    let mut canvas = RgbaImage::new(max_w, total_height);
    for p in canvas.pixels_mut() {
        *p = image::Rgba([255, 255, 255, 255]);
    }

    // Pass 2 — load, blit, drop one image at a time
    let mut current_y: u32 = 0;
    let mut blitted = 0usize;

    for path in image_paths {
        let img = match load_img(path) {
            Ok(i) => i,
            Err(_) => continue,
        };

        let (w, h) = (img.width(), img.height());
        let x_offset: u32 = match align_mode {
            "right" => max_w - w,
            "center" => (max_w - w) / 2,
            _ => 0,
        };

        image::imageops::overlay(&mut canvas, &img, x_offset as i64, current_y as i64);
        current_y += h + spacing;
        blitted += 1;
        // img is dropped here, freeing its pixel buffer immediately
    }

    if blitted == 0 {
        return Ok(false);
    }

    canvas
        .save(output_path)
        .map_err(|e| anyhow!("Failed to save: {}", e))?;
    Ok(true)
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn merge_images_vertical(
    image_paths: Vec<String>,
    output_path: String,
    spacing: u32,
    align_mode: String,
) -> PyResult<bool> {
    merge_images_vertical_core(&image_paths, &output_path, spacing, &align_mode)
        .map_err(|e| PyValueError::new_err(format!("{}", e)))
}

pub fn merge_images_grid_core(
    image_paths: &[String],
    output_path: &str,
    rows: u32,
    cols: u32,
    spacing: u32,
) -> Result<bool> {
    if image_paths.is_empty() {
        return Ok(false);
    }

    // Pass 1 — read headers only to find max cell dimensions
    let dims: Vec<(u32, u32)> = image_paths
        .iter()
        .filter_map(|p| read_dimensions(p).ok())
        .collect();

    if dims.is_empty() {
        return Ok(false);
    }

    let max_w = dims.iter().map(|&(w, _)| w).max().unwrap();
    let max_h = dims.iter().map(|&(_, h)| h).max().unwrap();

    let total_w = cols * max_w + (spacing * (cols - 1));
    let total_h = rows * max_h + (spacing * (rows - 1));

    let mut canvas = RgbaImage::new(total_w, total_h);
    for p in canvas.pixels_mut() {
        *p = image::Rgba([255, 255, 255, 255]);
    }

    // Pass 2 — load, blit, drop one image at a time
    let mut blitted = 0usize;

    for (idx, path) in image_paths.iter().enumerate() {
        let row = idx as u32 / cols;
        let col = idx as u32 % cols;
        if row >= rows {
            break;
        }

        let img = match load_img(path) {
            Ok(i) => i,
            Err(_) => continue,
        };

        let x = col * (max_w + spacing) + (max_w - img.width()) / 2;
        let y = row * (max_h + spacing) + (max_h - img.height()) / 2;

        image::imageops::overlay(&mut canvas, &img, x as i64, y as i64);
        blitted += 1;
        // img is dropped here, freeing its pixel buffer immediately
    }

    if blitted == 0 {
        return Ok(false);
    }

    canvas
        .save(output_path)
        .map_err(|e| anyhow!("Failed to save: {}", e))?;
    Ok(true)
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn merge_images_grid(
    image_paths: Vec<String>,
    output_path: String,
    rows: u32,
    cols: u32,
    spacing: u32,
) -> PyResult<bool> {
    merge_images_grid_core(&image_paths, &output_path, rows, cols, spacing)
        .map_err(|e| PyValueError::new_err(format!("{}", e)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{Rgb, RgbImage};
    use tempfile::tempdir;

    fn create_test_image(path: &str, w: u32, h: u32, color: [u8; 3]) {
        let mut img = RgbImage::new(w, h);
        for x in 0..w {
            for y in 0..h {
                img.put_pixel(x, y, Rgb(color));
            }
        }
        img.save(path).unwrap();
    }

    #[test]
    fn test_merge_horizontal() {
        let dir = tempdir().unwrap();
        let p1 = dir.path().join("1.png");
        let p2 = dir.path().join("2.png");
        let out = dir.path().join("out.png");

        create_test_image(p1.to_str().unwrap(), 100, 100, [255, 0, 0]);
        create_test_image(p2.to_str().unwrap(), 50, 50, [0, 255, 0]);

        let paths = vec![
            p1.to_str().unwrap().to_string(),
            p2.to_str().unwrap().to_string(),
        ];

        match merge_images_horizontal_core(&paths, out.to_str().unwrap(), 0, "top") {
            Ok(res) => assert!(res),
            Err(e) => panic!("Merge failed: {}", e),
        }

        let res_img = image::open(&out).unwrap();
        assert_eq!(res_img.width(), 150);
        assert_eq!(res_img.height(), 100);
    }

    #[test]
    fn test_merge_vertical() {
        let dir = tempdir().unwrap();
        let p1 = dir.path().join("1.png");
        let p2 = dir.path().join("2.png");
        let out = dir.path().join("out_v.png");

        create_test_image(p1.to_str().unwrap(), 100, 100, [255, 0, 0]);
        create_test_image(p2.to_str().unwrap(), 50, 50, [0, 255, 0]);

        let paths = vec![
            p1.to_str().unwrap().to_string(),
            p2.to_str().unwrap().to_string(),
        ];

        match merge_images_vertical_core(&paths, out.to_str().unwrap(), 0, "left") {
            Ok(res) => assert!(res),
            Err(e) => panic!("Merge failed: {}", e),
        }

        let res_img = image::open(&out).unwrap();
        assert_eq!(res_img.width(), 100);
        assert_eq!(res_img.height(), 150);
    }

    #[test]
    fn test_merge_horizontal_streaming_correct_dims() {
        // Verify that two-pass produces the same canvas size as the old one-pass code
        let dir = tempdir().unwrap();
        let paths: Vec<String> = (0..5u32)
            .map(|i| {
                let p = dir.path().join(format!("{}.png", i));
                create_test_image(p.to_str().unwrap(), 100 + i * 20, 80 + i * 10, [i as u8 * 50, 0, 0]);
                p.to_str().unwrap().to_string()
            })
            .collect();
        let out = dir.path().join("h_stream.png");
        assert!(merge_images_horizontal_core(&paths, out.to_str().unwrap(), 5, "center").unwrap());
        let img = image::open(&out).unwrap();
        // width = sum(100,120,140,160,180) + 4*5 spacing = 700 + 20 = 720
        assert_eq!(img.width(), 720);
        // height = max(80,90,100,110,120) = 120
        assert_eq!(img.height(), 120);
    }

    #[test]
    fn test_merge_vertical_streaming_correct_dims() {
        let dir = tempdir().unwrap();
        let paths: Vec<String> = (0..4u32)
            .map(|i| {
                let p = dir.path().join(format!("{}.png", i));
                create_test_image(p.to_str().unwrap(), 60 + i * 10, 40 + i * 15, [0, i as u8 * 60, 0]);
                p.to_str().unwrap().to_string()
            })
            .collect();
        let out = dir.path().join("v_stream.png");
        assert!(merge_images_vertical_core(&paths, out.to_str().unwrap(), 2, "center").unwrap());
        let img = image::open(&out).unwrap();
        // height = sum(40,55,70,85) + 3*2 = 250 + 6 = 256
        assert_eq!(img.height(), 256);
        // width = max(60,70,80,90) = 90
        assert_eq!(img.width(), 90);
    }

    #[test]
    fn test_merge_grid_streaming_correct_dims() {
        let dir = tempdir().unwrap();
        let paths: Vec<String> = (0..6u32)
            .map(|i| {
                let p = dir.path().join(format!("{}.png", i));
                create_test_image(p.to_str().unwrap(), 50, 50, [i as u8 * 40, 0, 0]);
                p.to_str().unwrap().to_string()
            })
            .collect();
        let out = dir.path().join("g_stream.png");
        assert!(merge_images_grid_core(&paths, out.to_str().unwrap(), 2, 3, 10).unwrap());
        let img = image::open(&out).unwrap();
        // total_w = 3*50 + 2*10 = 170; total_h = 2*50 + 1*10 = 110
        assert_eq!(img.width(), 170);
        assert_eq!(img.height(), 110);
    }

    #[test]
    fn test_empty_paths_returns_false() {
        let dir = tempdir().unwrap();
        let out = dir.path().join("empty.png");
        let paths: Vec<String> = vec![];
        assert!(!merge_images_horizontal_core(&paths, out.to_str().unwrap(), 0, "top").unwrap());
        assert!(!merge_images_vertical_core(&paths, out.to_str().unwrap(), 0, "left").unwrap());
        assert!(!merge_images_grid_core(&paths, out.to_str().unwrap(), 2, 2, 0).unwrap());
    }
}
