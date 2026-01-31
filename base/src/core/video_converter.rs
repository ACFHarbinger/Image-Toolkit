#[cfg(feature = "python")]
use pyo3::prelude::*;
#[cfg(feature = "python")]
use std::fs;
#[cfg(feature = "python")]
use std::process::Command;

#[cfg(feature = "python")]
#[pyfunction]
pub fn convert_video(
    py: Python,
    input_path: String,
    output_path: String,
    delete_original: bool,
) -> PyResult<bool> {
    py.detach(|| {
        let status = Command::new("ffmpeg")
            .args(&[
                "-y", // Overwrite output files
                "-i",
                &input_path,
                &output_path,
            ])
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .status();

        match status {
            Ok(s) => {
                let success: bool = s.success();
                if success {
                    if delete_original {
                        let _ = fs::remove_file(input_path);
                    }
                    Ok(true)
                } else {
                    Ok(false)
                }
            }
            Err(_) => Ok(false),
        }
    })
}
