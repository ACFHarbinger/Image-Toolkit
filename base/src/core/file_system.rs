use pyo3::prelude::*;
use rayon::prelude::*;
use std::fs;
use std::path::Path;
use walkdir::WalkDir;

#[pyfunction]
pub fn get_files_by_extension(
    py: Python,
    directory: String,
    extension: String,
    recursive: bool,
) -> PyResult<Vec<String>> {
    let ext = extension.trim_start_matches('.').to_lowercase();

    let results: Vec<String> = py.allow_threads(|| {
        let walker = if recursive {
            WalkDir::new(&directory).into_iter()
        } else {
            WalkDir::new(&directory).max_depth(1).into_iter()
        };

        walker
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .filter(|e| {
                e.path()
                    .extension()
                    .and_then(|e| e.to_str())
                    .map(|e| e.to_lowercase() == ext)
                    .unwrap_or(false)
            })
            .map(|e| e.path().to_string_lossy().to_string())
            .collect()
    });

    Ok(results)
}

#[pyfunction]
pub fn delete_files_by_extensions(
    py: Python,
    directory: String,
    extensions: Vec<String>,
) -> PyResult<usize> {
    let exts: Vec<String> = extensions
        .iter()
        .map(|e| e.trim_start_matches('.').to_lowercase())
        .collect();

    let count = py.allow_threads(|| {
        WalkDir::new(&directory)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .filter(|e| {
                e.path()
                    .extension()
                    .and_then(|s| s.to_str())
                    .map(|s| exts.contains(&s.to_lowercase()))
                    .unwrap_or(false)
            })
            .par_bridge() // Parallel deletion
            .map(|e| {
                if fs::remove_file(e.path()).is_ok() {
                    1
                } else {
                    0
                }
            })
            .sum()
    });

    Ok(count)
}

#[pyfunction]
pub fn delete_path(py: Python, path: String) -> PyResult<bool> {
    py.allow_threads(|| {
        let p = Path::new(&path);
        if !p.exists() {
            return Ok(false);
        }

        if p.is_dir() {
            match fs::remove_dir_all(p) {
                Ok(_) => Ok(true),
                Err(_) => Ok(false),
            }
        } else {
            match fs::remove_file(p) {
                Ok(_) => Ok(true),
                Err(_) => Ok(false),
            }
        }
    })
}
