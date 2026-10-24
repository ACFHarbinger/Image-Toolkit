//! External browser escape hatch restricted to the local ComfyUI origin.

use std::process::Command;

fn validate_url(value: &str) -> Result<tauri::Url, String> {
    let url = tauri::Url::parse(value).map_err(|_| "Invalid ComfyUI URL")?;
    if !matches!(url.scheme(), "http" | "https")
        || !matches!(
            url.host_str(),
            Some("localhost" | "127.0.0.1" | "[::1]" | "::1")
        )
        || !url.username().is_empty()
        || url.password().is_some()
    {
        return Err("Only credential-free loopback HTTP(S) ComfyUI URLs may be opened".into());
    }
    Ok(url)
}

#[tauri::command]
pub async fn open_comfy_browser(url: String) -> Result<(), String> {
    let url = validate_url(&url)?;
    tauri::async_runtime::spawn_blocking(move || {
        #[cfg(target_os = "linux")]
        let mut command = Command::new("xdg-open");
        #[cfg(target_os = "macos")]
        let mut command = Command::new("open");
        #[cfg(target_os = "windows")]
        let mut command = {
            let mut cmd = Command::new("rundll32.exe");
            cmd.arg("url.dll,FileProtocolHandler");
            cmd
        };
        let status = command
            .arg(url.as_str())
            .status()
            .map_err(|error| format!("Failed to launch the default browser: {error}"))?;
        if !status.success() {
            return Err("The default browser opener failed".to_string());
        }
        Ok(())
    })
    .await
    .map_err(|error| error.to_string())?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn permits_only_credential_free_loopback_web_urls() {
        for url in [
            "http://127.0.0.1:8188",
            "https://localhost:8443/app",
            "http://[::1]:8188",
        ] {
            assert!(validate_url(url).is_ok());
        }
        for url in [
            "https://remote.example",
            "file:///tmp/a",
            "javascript:alert(1)",
            "http://user:secret@localhost:8188",
            "http://localhost.evil:8188",
        ] {
            assert!(validate_url(url).is_err());
        }
    }
}
