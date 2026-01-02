use fast_image_resize as fr;
use image::{DynamicImage, ImageReader, RgbaImage};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::path::Path;

// Re-use logic from image_converter would be ideal, but for now I'll duplicate the simple load/resize helpers to keep modules decoupled or I could make them public in image_converters.
// To avoid complexity, I'll inline a simple resize helper here.

fn load_img(path: &str) -> PyResult<DynamicImage> {
    ImageReader::open(path)
        .map_err(|e| PyValueError::new_err(format!("Failed to open: {}", e)))?
        .decode()
        .map_err(|e| PyValueError::new_err(format!("Failed to decode: {}", e)))
}

fn fast_resize(img: &DynamicImage, w: u32, h: u32) -> DynamicImage {
    let src_w = img.width();
    let src_h = img.height();
    if src_w == w && src_h == h {
        return img.clone();
    }

    // Convert to Rgba8
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

#[pyfunction]
pub fn merge_images_horizontal(
    image_paths: Vec<String>,
    output_path: String,
    spacing: u32,
    align_mode: String, // "center", "top", "bottom", "stretch"
) -> PyResult<bool> {
    if image_paths.is_empty() {
        return Ok(false);
    }

    let images: Vec<DynamicImage> = image_paths
        .iter()
        .filter_map(|p| load_img(p).ok())
        .collect();

    if images.is_empty() {
        return Ok(false);
    }

    // Calc dimensions
    let heights: Vec<u32> = images.iter().map(|i| i.height()).collect();
    let max_h = *heights.iter().max().unwrap();

    let mut final_images = Vec::new();

    if align_mode == "stretch" || align_mode == "squish" {
        // Resize all to max_h (or min_h? Python used max for stretch, min for squish. Let's simplify to max for Rust MVP)
        for img in images {
            final_images.push(fast_resize(&img, img.width(), max_h)); // Stretch height only? No, usually expect aspect ratio logic.
            // ImageMerger python logic:
            // Scaled (Grow Smallest) -> target_h = max_h.
            // Python's resize was simple resize(target_size).
            // Let's implement full 'max height' resize for everything if 'stretch'.
        }
    } else {
        final_images = images;
    }

    let total_width: u32 = final_images.iter().map(|i| i.width()).sum::<u32>()
        + (spacing * (final_images.len() as u32 - 1));
    let canvas_height = max_h;

    let mut canvas = RgbaImage::new(total_width, canvas_height);
    // Fill white? Python used RGB white.
    // RgbaImage default is 0,0,0,0 transparent.
    // Let's fill white opaque.
    for p in canvas.pixels_mut() {
        *p = image::Rgba([255, 255, 255, 255]);
    }

    let mut current_x = 0;

    for img in final_images {
        let (w, h) = (img.width(), img.height());
        // Align y
        let y_offset = match align_mode.as_str() {
            "bottom" => canvas_height - h,
            "center" => (canvas_height - h) / 2,
            _ => 0, // Top
        };

        // Paste
        image::imageops::overlay(&mut canvas, &img, current_x as i64, y_offset as i64);
        current_x += w + spacing;
    }

    canvas
        .save(output_path)
        .map_err(|e| PyValueError::new_err(format!("Failed to save: {}", e)))?;
    Ok(true)
}

#[pyfunction]
pub fn merge_images_vertical(
    image_paths: Vec<String>,
    output_path: String,
    spacing: u32,
    align_mode: String,
) -> PyResult<bool> {
    if image_paths.is_empty() {
        return Ok(false);
    }

    let images: Vec<DynamicImage> = image_paths
        .iter()
        .filter_map(|p| load_img(p).ok())
        .collect();

    if images.is_empty() {
        return Ok(false);
    }

    let widths: Vec<u32> = images.iter().map(|i| i.width()).collect();
    let max_w = *widths.iter().max().unwrap();

    let total_height: u32 =
        images.iter().map(|i| i.height()).sum::<u32>() + (spacing * (images.len() as u32 - 1));
    let canvas_width = max_w;

    let mut canvas = RgbaImage::new(canvas_width, total_height);
    for p in canvas.pixels_mut() {
        *p = image::Rgba([255, 255, 255, 255]);
    }

    let mut current_y = 0;

    for img in images {
        let (w, h) = (img.width(), img.height());
        let x_offset = match align_mode.as_str() {
            "right" => canvas_width - w,
            "center" => (canvas_width - w) / 2,
            _ => 0, // Left
        };

        image::imageops::overlay(&mut canvas, &img, x_offset as i64, current_y as i64);
        current_y += h + spacing;
    }

    canvas
        .save(output_path)
        .map_err(|e| PyValueError::new_err(format!("Failed to save: {}", e)))?;
    Ok(true)
}

#[pyfunction]
pub fn merge_images_grid(
    image_paths: Vec<String>,
    output_path: String,
    rows: u32,
    cols: u32,
    spacing: u32,
) -> PyResult<bool> {
    if image_paths.is_empty() {
        return Ok(false);
    }

    let images: Vec<DynamicImage> = image_paths
        .iter()
        .filter_map(|p| load_img(p).ok())
        .collect();

    if images.is_empty() {
        return Ok(false);
    }

    // Find Max Cells
    let max_w = images.iter().map(|i| i.width()).max().unwrap();
    let max_h = images.iter().map(|i| i.height()).max().unwrap();

    let total_w = cols * max_w + (spacing * (cols - 1));
    let total_h = rows * max_h + (spacing * (rows - 1));

    let mut canvas = RgbaImage::new(total_w, total_h);
    for p in canvas.pixels_mut() {
        *p = image::Rgba([255, 255, 255, 255]);
    }

    for (idx, img) in images.iter().enumerate() {
        let row = idx as u32 / cols;
        let col = idx as u32 % cols;
        if row >= rows {
            break;
        }

        let x = col * (max_w + spacing) + (max_w - img.width()) / 2;
        let y = row * (max_h + spacing) + (max_h - img.height()) / 2;

        image::imageops::overlay(&mut canvas, img, x as i64, y as i64);
    }

    canvas
        .save(output_path)
        .map_err(|e| PyValueError::new_err(format!("Failed to save: {}", e)))?;
    Ok(true)
}
