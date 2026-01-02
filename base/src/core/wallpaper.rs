use pyo3::prelude::*;
use std::process::Command;

#[pyfunction]
pub fn set_wallpaper_gnome(uri: String, mode: String) -> PyResult<bool> {
    // mode: scaled, spanned, none, wallpaper, centered, stretched, zoom
    let _ = Command::new("gsettings")
        .args(&["set", "org.gnome.desktop.background", "picture-uri", &uri])
        .output();

    let _ = Command::new("gsettings")
        .args(&[
            "set",
            "org.gnome.desktop.background",
            "picture-options",
            &mode,
        ])
        .output();

    Ok(true)
}

#[pyfunction]
pub fn run_qdbus_command(command: String) -> PyResult<String> {
    let output = Command::new("sh").arg("-c").arg(command).output()?;

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}
