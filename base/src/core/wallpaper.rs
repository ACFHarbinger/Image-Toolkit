#[cfg(feature = "python")]
use pyo3::prelude::*;
use std::process::Command;

// Standard Rust functions for internal use (e.g. by slideshow_daemon)

pub fn set_wallpaper_gnome_core(uri: &str, mode: &str) -> std::io::Result<()> {
    Command::new("gsettings")
        .args(&["set", "org.gnome.desktop.background", "picture-uri", uri])
        .output()?;

    Command::new("gsettings")
        .args(&[
            "set",
            "org.gnome.desktop.background",
            "picture-options",
            mode,
        ])
        .output()?;

    Ok(())
}

pub fn evaluate_kde_script_core(qdbus_bin: &str, script: &str) -> Result<String, String> {
    let output = Command::new(qdbus_bin)
        .arg("org.kde.plasmashell")
        .arg("/PlasmaShell")
        .arg("org.kde.PlasmaShell.evaluateScript")
        .arg(script)
        .output()
        .map_err(|e| format!("Failed to execute qdbus: {}", e))?;

    if !output.status.success() {
        return Err(format!(
            "QDBus failed: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

#[derive(Debug, Clone)]
pub struct KdeDesktop {
    pub index: u32,
    pub screen: i32,
    pub x: i32,
    pub y: i32,
}

pub fn get_kde_desktops_core(qdbus_bin: &str) -> Result<Vec<KdeDesktop>, String> {
    let script = r#"
        var ds = desktops();
        var output = [];
        for (var i = 0; i < ds.length; i++) {
            var d = ds[i];
            var s = d.screen;
            if (s < 0) continue; 
            try {
                var rect = screenGeometry(s);
                output.push(i + ":" + s + ":" + rect.x + ":" + rect.y);
            } catch(e) {}
        }
        print(output.join("\n"));
    "#;
    let result = evaluate_kde_script_core(qdbus_bin, script)?;
    let mut desktops = Vec::new();
    for line in result.lines() {
        let parts: Vec<&str> = line.split(':').collect();
        if parts.len() >= 4 {
            if let (Ok(index), Ok(screen), Ok(x), Ok(y)) = (
                parts[0].parse::<u32>(),
                parts[1].parse::<i32>(),
                parts[2].parse::<i32>(),
                parts[3].parse::<i32>(),
            ) {
                desktops.push(KdeDesktop {
                    index,
                    screen,
                    x,
                    y,
                });
            }
        }
    }
    Ok(desktops)
}

// PyO3 Wrappers

#[cfg(feature = "python")]
#[pyfunction]
pub fn set_wallpaper_gnome(uri: String, mode: String) -> PyResult<bool> {
    set_wallpaper_gnome_core(&uri, &mode)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;
    Ok(true)
}

#[cfg(feature = "python")]
#[pyfunction]
pub fn evaluate_kde_script(qdbus_bin: String, script: String) -> PyResult<String> {
    evaluate_kde_script_core(&qdbus_bin, &script)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(e))
}
