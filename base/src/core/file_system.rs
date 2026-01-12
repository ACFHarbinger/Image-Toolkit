use pyo3::prelude::*;
use rayon::prelude::*;
use std::fs;
use std::path::Path;
use walkdir::WalkDir;

// Core (non-Python) helper for reuse by Tauri and other Rust callers.
pub fn get_files_by_extension_core(
    directory: &str,
    extension: &str,
    recursive: bool,
) -> Vec<String> {
    let ext = extension.trim_start_matches('.').to_lowercase();
    let walker = if recursive {
        WalkDir::new(directory).into_iter()
    } else {
        WalkDir::new(directory).max_depth(1).into_iter()
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
}

pub fn delete_files_by_extensions_core(directory: &str, extensions: &[String]) -> usize {
    let exts: Vec<String> = extensions
        .iter()
        .map(|e| e.trim_start_matches('.').to_lowercase())
        .collect();

    WalkDir::new(directory)
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
}

pub fn delete_path_core(path: &str) -> bool {
    let p = Path::new(path);
    if !p.exists() {
        return false;
    }

    if p.is_dir() {
        fs::remove_dir_all(p).is_ok()
    } else {
        fs::remove_file(p).is_ok()
    }
}

#[pyfunction]
pub fn get_files_by_extension(
    py: Python,
    directory: String,
    extension: String,
    recursive: bool,
) -> PyResult<Vec<String>> {
    let results: Vec<String> =
        py.detach(|| get_files_by_extension_core(&directory, &extension, recursive));
    Ok(results)
}

#[pyfunction]
pub fn delete_files_by_extensions(
    py: Python,
    directory: String,
    extensions: Vec<String>,
) -> PyResult<usize> {
    let count = py.detach(|| delete_files_by_extensions_core(&directory, &extensions));
    Ok(count)
}

#[pyfunction]
pub fn delete_path(py: Python, path: String) -> PyResult<bool> {
    let res = py.detach(|| delete_path_core(&path));
    Ok(res)
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::Python;
    use std::fs::File;
    use tempfile::tempdir;

    #[test]
    fn test_get_files_by_extension() {
        // Setup
        let dir = tempdir().unwrap();
        let file1 = dir.path().join("test1.txt");
        let file2 = dir.path().join("test2.png");
        let sub_dir = dir.path().join("sub");
        fs::create_dir(&sub_dir).unwrap();
        let file3 = sub_dir.join("test3.txt");

        File::create(&file1).unwrap();
        File::create(&file2).unwrap();
        File::create(&file3).unwrap();

        Python::initialize();
        Python::attach(|py| {
            // Test non-recursive
            let files = get_files_by_extension(
                py,
                dir.path().to_str().unwrap().to_string(),
                "txt".to_string(),
                false,
            )
            .unwrap();
            assert_eq!(files.len(), 1);
            assert!(files[0].contains("test1.txt"));

            // Test recursive
            let files_rec = get_files_by_extension(
                py,
                dir.path().to_str().unwrap().to_string(),
                ".txt".to_string(),
                true,
            )
            .unwrap();
            assert_eq!(files_rec.len(), 2);
        });
    }

    #[test]
    fn test_delete_path() {
        let dir = tempdir().unwrap();
        let file = dir.path().join("delete_me.txt");
        File::create(&file).unwrap();

        Python::initialize();
        Python::attach(|py| {
            let res = delete_path(py, file.to_str().unwrap().to_string()).unwrap();
            assert!(res);
            assert!(!file.exists());

            let res_fail = delete_path(py, file.to_str().unwrap().to_string()).unwrap();
            assert!(!res_fail);
        });
    }

    #[test]
    fn test_delete_files_by_extensions() {
        let dir = tempdir().unwrap();
        let f1 = dir.path().join("a.tmp");
        let f2 = dir.path().join("b.tmp");
        let f3 = dir.path().join("c.keep");
        File::create(&f1).unwrap();
        File::create(&f2).unwrap();
        File::create(&f3).unwrap();

        Python::initialize();
        Python::attach(|py| {
            let count = delete_files_by_extensions(
                py,
                dir.path().to_str().unwrap().to_string(),
                vec!["tmp".to_string()],
            )
            .unwrap();
            assert_eq!(count, 2);
            assert!(!f1.exists());
            assert!(!f2.exists());
            assert!(f3.exists());
        });
    }
}
