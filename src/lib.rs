use fast_image_resize as fr;
use image::ImageReader;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use rayon::prelude::*;

#[pyfunction]
fn load_image_batch(
    py: Python,
    paths: Vec<String>,
    thumbnail_size: u32,
) -> PyResult<Vec<(String, Py<PyBytes>, u32, u32)>> {
    let results: Vec<(String, Option<(Vec<u8>, u32, u32)>)> = paths
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
        .collect();

    // Convert to Python response
    let mut py_results = Vec::new();
    for (path, data) in results {
        if let Some((buf, w, h)) = data {
            py_results.push((path, PyBytes::new(py, &buf).into(), w, h));
        }
    }

    Ok(py_results)
}

#[pymodule]
fn native_imaging(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(load_image_batch, m)?)?;
    Ok(())
}
