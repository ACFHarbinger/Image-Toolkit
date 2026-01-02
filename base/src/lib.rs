use fast_image_resize as fr;
use image::ImageReader;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use rayon::prelude::*;
use std::process::Command;
use walkdir::WalkDir;

#[pyfunction]
pub fn load_image_batch(
    py: Python,
    paths: Vec<String>,
    thumbnail_size: u32,
) -> PyResult<Vec<(String, Py<PyBytes>, u32, u32)>> {
    let results: Vec<(String, Option<(Vec<u8>, u32, u32)>)> = py.allow_threads(|| {
        paths
            .par_iter()
            .map(|path| {
                let res =
                    (|| -> Result<(Vec<u8>, u32, u32), Box<dyn std::error::Error + Send + Sync>> {
                        // 1. Load and decode image
                        let img = ImageReader::open(path)?.decode()?;
                        let width = img.width();
                        let height = img.height();

                        // 2. Calculate dimensions for aspect ratio
                        let aspect_ratio = width as f32 / height as f32;
                        let (new_w, new_h) = if width > height {
                            (
                                thumbnail_size,
                                (thumbnail_size as f32 / aspect_ratio) as u32,
                            )
                        } else {
                            (
                                (thumbnail_size as f32 * aspect_ratio) as u32,
                                thumbnail_size,
                            )
                        };

                        // 3. Resize using fast_image_resize
                        let src_image = fr::images::Image::from_vec_u8(
                            width,
                            height,
                            img.to_rgba8().into_raw(),
                            fr::PixelType::U8x4,
                        )?;

                        let mut dst_image = fr::images::Image::new(new_w, new_h, fr::PixelType::U8x4);

                        let mut resizer = fr::Resizer::new();
                        resizer.resize(&src_image, &mut dst_image, None)?;

                        Ok((dst_image.buffer().to_vec(), new_w, new_h))
                    })();

                match res {
                    Ok((buffer, w, h)) => (path.clone(), Some((buffer, w, h))),
                    Err(_) => (path.clone(), None),
                }
            })
            .collect()
    });

    // Convert to Python response
    let mut py_results = Vec::new();
    for (path, data) in results {
        if let Some((buf, w, h)) = data {
            py_results.push((path, PyBytes::new(py, &buf).into(), w, h));
        }
    }

    Ok(py_results)
}

#[pyfunction]
pub fn scan_files(
    py: Python,
    directories: Vec<String>,
    extensions: Vec<String>,
    recursive: bool,
) -> PyResult<Vec<String>> {
    py.allow_threads(|| {
        let extensions: Vec<String> = extensions
            .iter()
            .map(|e| e.to_lowercase().replace(".", ""))
            .collect();

        let results: Vec<Vec<String>> = directories
            .par_iter()
            .map(|dir| {
                let mut found = Vec::new();
                let mut walker = WalkDir::new(dir);
                if !recursive {
                    walker = walker.max_depth(1);
                }

                for entry in walker
                    .into_iter()
                    .filter_entry(|e| {
                        !e.file_name()
                            .to_str()
                            .map(|s| s.starts_with('.'))
                            .unwrap_or(false)
                    })
                    .filter_map(|e| e.ok())
                {
                    if entry.file_type().is_file() {
                        if let Some(ext) = entry.path().extension().and_then(|s| s.to_str()) {
                            let ext_lower = ext.to_lowercase();
                            if extensions.iter().any(|e| e == &ext_lower) {
                                found.push(entry.path().to_string_lossy().to_string());
                            }
                        }
                    }
                }
                found
            })
            .collect();

        let mut flat_results = Vec::new();
        for mut sub_results in results {
            flat_results.append(&mut sub_results);
        }
        flat_results.sort();
        Ok(flat_results)
    })
}

#[pyfunction]
pub fn extract_video_thumbnails_batch(
    py: Python,
    paths: Vec<String>,
    thumbnail_size: u32,
) -> PyResult<Vec<(String, Py<PyBytes>, u32, u32)>> {
    let results: Vec<(String, Option<(Vec<u8>, u32, u32)>)> = py.allow_threads(|| {
        paths
            .par_iter()
            .map(|path| {
                let res =
                    (|| -> Result<(Vec<u8>, u32, u32), Box<dyn std::error::Error + Send + Sync>> {
                        // Try multiple timestamps: 10s, 1s, 0s
                        let timestamps = ["00:00:10", "00:00:01", "00:00:00"];
                        let mut last_err = None;

                        for ss in timestamps {
                            let output = Command::new("ffmpeg")
                                .args(&[
                                    "-ss",
                                    ss,
                                    "-i",
                                    path,
                                    "-frames:v",
                                    "1",
                                    "-f",
                                    "image2",
                                    "-c:v",
                                    "mjpeg",
                                    "pipe:1",
                                ])
                                .output();

                            match output {
                                Ok(out) if out.status.success() && !out.stdout.is_empty() => {
                                    // Decode MJPEG from stdout
                                    let img = image::load_from_memory(&out.stdout)?;
                                    let width = img.width();
                                    let height = img.height();

                                    // Resize logic (redundant with image loading but keep it for consistency)
                                    let aspect_ratio = width as f32 / height as f32;
                                    let (new_w, new_h) = if width > height {
                                        (
                                            thumbnail_size,
                                            (thumbnail_size as f32 / aspect_ratio) as u32,
                                        )
                                    } else {
                                        (
                                            (thumbnail_size as f32 * aspect_ratio) as u32,
                                            thumbnail_size,
                                        )
                                    };

                                    let src_image = fr::images::Image::from_vec_u8(
                                        width,
                                        height,
                                        img.to_rgba8().into_raw(),
                                        fr::PixelType::U8x4,
                                    )?;

                                    let mut dst_image =
                                        fr::images::Image::new(new_w, new_h, fr::PixelType::U8x4);
                                    let mut resizer = fr::Resizer::new();
                                    resizer.resize(&src_image, &mut dst_image, None)?;

                                    return Ok((dst_image.buffer().to_vec(), new_w, new_h));
                                }
                                Ok(out) => {
                                    last_err = Some(format!(
                                        "ffmpeg failed for {}: status={:?}, stderr={}",
                                        path,
                                        out.status,
                                        String::from_utf8_lossy(&out.stderr)
                                    ));
                                }
                                Err(e) => {
                                    last_err =
                                        Some(format!("Failed to execute ffmpeg for {}: {}", path, e));
                                }
                            }
                        }
                        Err(last_err
                            .unwrap_or_else(|| "No frames extracted".to_string())
                            .into())
                    })();

                match res {
                    Ok((buffer, w, h)) => (path.clone(), Some((buffer, w, h))),
                    Err(_) => (path.clone(), None),
                }
            })
            .collect()
    });

    let mut py_results = Vec::new();
    for (path, data) in results {
        if let Some((buf, w, h)) = data {
            py_results.push((path, PyBytes::new(py, &buf).into(), w, h));
        }
    }

    Ok(py_results)
}

pub mod core;
pub mod web;

use core::file_system::*;
use core::image_converter::*;
use core::image_finder::*;
use core::image_merger::*;
use core::video_converter::*;
use core::wallpaper::*;
use web::web_requests::*;
use web::*;

#[pymodule]
fn base(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(load_image_batch, m)?)?;
    m.add_function(wrap_pyfunction!(scan_files, m)?)?;
    m.add_function(wrap_pyfunction!(extract_video_thumbnails_batch, m)?)?;

    // Core Functions
    m.add_function(wrap_pyfunction!(convert_single_image, m)?)?;
    m.add_function(wrap_pyfunction!(convert_image_batch, m)?)?;
    m.add_function(wrap_pyfunction!(convert_video, m)?)?;
    m.add_function(wrap_pyfunction!(set_wallpaper_gnome, m)?)?;
    m.add_function(wrap_pyfunction!(run_qdbus_command, m)?)?;
    m.add_function(wrap_pyfunction!(run_web_requests_sequence, m)?)?;
    m.add_function(wrap_pyfunction!(run_board_crawler, m)?)?;
    m.add_function(wrap_pyfunction!(run_reverse_image_search, m)?)?;
    m.add_function(wrap_pyfunction!(run_sync, m)?)?;

    // File System
    m.add_function(wrap_pyfunction!(get_files_by_extension, m)?)?;
    m.add_function(wrap_pyfunction!(delete_files_by_extensions, m)?)?;
    m.add_function(wrap_pyfunction!(delete_path, m)?)?;

    // Image Finder
    m.add_function(wrap_pyfunction!(find_duplicate_images, m)?)?;
    m.add_function(wrap_pyfunction!(find_similar_images_phash, m)?)?;

    // Image Merger
    m.add_function(wrap_pyfunction!(merge_images_horizontal, m)?)?;
    m.add_function(wrap_pyfunction!(merge_images_vertical, m)?)?;
    m.add_function(wrap_pyfunction!(merge_images_grid, m)?)?;

    Ok(())
}
