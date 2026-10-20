//! Talk to #877's `GuiInstance` so a second shell focuses the first.

use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use tauri::AppHandle;

fn repo_root() -> Option<PathBuf> {
    let mut dir = std::env::current_dir().ok()?;
    for _ in 0..8 {
        if dir.join("pyproject.toml").exists() && dir.join("middleware").is_dir() {
            return Some(dir);
        }
        dir = dir.parent()?.to_path_buf();
    }
    None
}

fn python_bin() -> String {
    std::env::var("IMAGE_TOOLKIT_PYTHON").unwrap_or_else(|_| "python3".to_string())
}

fn apply_venv_path(command: &mut Command, root: &Path) {
    let venv_bin = root.join(".venv").join("bin");
    if !venv_bin.is_dir() {
        return;
    }
    let extra = venv_bin.display().to_string();
    let path = match std::env::var("PATH") {
        Ok(path) => format!("{extra}:{path}"),
        Err(_) => extra,
    };
    command.env("PATH", path);
}

pub fn start(app: &AppHandle) {
    if let Err(err) = spawn(app) {
        log::warn!("gui gate skipped: {err}");
    }
}

fn spawn(app: &AppHandle) -> Result<(), String> {
    let data_dir = crate::window_registry::data_dir();
    let mut command = Command::new(python_bin());
    if let Some(root) = repo_root() {
        apply_venv_path(&mut command, &root);
        command.current_dir(root);
    }
    command
        .args([
            "-m",
            "middleware.src.supervisor.gui_shell",
            "--data-dir",
            &data_dir.to_string_lossy(),
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    let mut child = command.spawn().map_err(|err| err.to_string())?;
    let stdout = child.stdout.take().ok_or("gui_shell has no stdout")?;
    let mut lines = BufReader::new(stdout).lines();
    let first = lines
        .next()
        .transpose()
        .map_err(|err| err.to_string())?
        .unwrap_or_default();
    match first.trim() {
        "FOCUSED_OTHER" => {
            app.exit(0);
            return Ok(());
        }
        "ACQUIRED" => {}
        other => {
            log::warn!("gui_shell said {other:?}; continuing without the gate");
            return Ok(());
        }
    }
    let handle = app.clone();
    thread::spawn(move || {
        for line in lines.flatten() {
            if line.trim() == "FOCUS" {
                let _ = crate::window_registry::restore(&handle);
            }
        }
        let _ = child.wait();
    });
    Ok(())
}
