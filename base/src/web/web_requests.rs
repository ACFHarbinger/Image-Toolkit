use anyhow::{Context, Result};
use pyo3::prelude::*;
use reqwest::blocking::{Client, Response};
use serde_json::Value;
use std::collections::HashMap;
use std::fs;
use std::path::Path;
use std::time::Duration;

#[pyfunction]
pub fn run_web_requests_sequence(
    py: Python<'_>,
    config: String,
    callback_obj: PyObject,
) -> PyResult<String> {
    let config_val: Value = serde_json::from_str(&config).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Invalid JSON: {}", e))
    })?;

    let base_url = config_val
        .get("base_url")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let requests = config_val
        .get("requests")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let actions = config_val
        .get("actions")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let client = Client::builder()
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to create client: {}",
                e
            ))
        })?;

    emit_status(
        py,
        &callback_obj,
        &format!("Starting request sequence for {}", base_url),
    )?;

    for (i, req) in requests.iter().enumerate() {
        // Check for cancellation (if the python object has a flag)
        if let Ok(is_running) = callback_obj.getattr(py, "_is_running") {
            if !is_running.extract::<bool>(py)? {
                emit_status(py, &callback_obj, "Request sequence cancelled.")?;
                return Ok("Cancelled.".to_string());
            }
        }

        let req_type = req.get("type").and_then(|v| v.as_str()).unwrap_or("GET");
        let param = req.get("param").and_then(|v| v.as_str()).unwrap_or("");

        let mut url_to_request = base_url.to_string();
        emit_status(
            py,
            &callback_obj,
            &format!(
                "--- Request {}/{}: [{}] ---",
                i + 1,
                requests.len(),
                req_type
            ),
        )?;

        let response_res = match req_type {
            "GET" => {
                if !param.is_empty() {
                    url_to_request = format!(
                        "{}/{}",
                        base_url.trim_end_matches('/'),
                        param.trim_start_matches('/')
                    );
                }
                emit_status(
                    py,
                    &callback_obj,
                    &format!("Executing GET: {}", url_to_request),
                )?;
                client.get(&url_to_request).send()
            }
            "POST" => {
                let post_data = parse_post_data(param);
                emit_status(
                    py,
                    &callback_obj,
                    &format!(
                        "Executing POST: {} with data: {:?}",
                        url_to_request, post_data
                    ),
                )?;
                client.post(&url_to_request).form(&post_data).send()
            }
            _ => {
                emit_error(
                    py,
                    &callback_obj,
                    &format!("Unsupported request type: {}", req_type),
                )?;
                continue;
            }
        };

        match response_res {
            Ok(response) => {
                let status = response.status();
                emit_status(
                    py,
                    &callback_obj,
                    &format!("Request complete. Status: {}", status),
                )?;

                if !status.is_success() {
                    emit_error(
                        py,
                        &callback_obj,
                        &format!("Request failed: HTTP {}", status),
                    )?;
                    continue;
                }

                // Run actions
                if let Err(e) = run_actions(py, &callback_obj, response, &actions) {
                    emit_error(
                        py,
                        &callback_obj,
                        &format!("Action execution failed: {}", e),
                    )?;
                }
            }
            Err(e) => {
                emit_error(py, &callback_obj, &format!("Request failed: {}", e))?;
            }
        }

        std::thread::sleep(Duration::from_millis(500));
    }

    emit_status(py, &callback_obj, "--- All requests finished. ---")?;
    Ok("All requests finished.".to_string())
}

fn emit_status(py: Python<'_>, obj: &PyObject, msg: &str) -> PyResult<()> {
    obj.call_method1(py, "on_status_emitted", (msg,))?;
    Ok(())
}

fn emit_error(py: Python<'_>, obj: &PyObject, msg: &str) -> PyResult<()> {
    obj.call_method1(py, "on_error_emitted", (msg,))?;
    Ok(())
}

fn parse_post_data(param_str: &str) -> HashMap<String, String> {
    let mut data = HashMap::new();
    if param_str.is_empty() {
        return data;
    }
    for pair in param_str.split(',') {
        if let Some((key, val)) = pair.split_once(':') {
            data.insert(key.trim().to_string(), val.trim().to_string());
        }
    }
    data
}

fn run_actions(
    py: Python<'_>,
    callback_obj: &PyObject,
    response: Response,
    actions: &Vec<Value>,
) -> Result<()> {
    // We need to consume the response body for some actions.
    // However, some actions only need headers or URL.
    // To handle multiple actions on the same response, we might need to buffer the response content.

    let url = response.url().to_string();
    let status = response.status();
    let headers = response.headers().clone();

    // Buffer content if needed
    let mut content: Option<Vec<u8>> = None;

    for action in actions {
        let action_type = action.get("type").and_then(|v| v.as_str()).unwrap_or("");

        match action_type {
            "Print Response URL" => {
                let _ = emit_status(
                    py,
                    callback_obj,
                    &format!("  > Action: Response URL: {}", url),
                );
            }
            "Print Response Status Code" => {
                let _ = emit_status(
                    py,
                    callback_obj,
                    &format!("  > Action: Status Code: {}", status),
                );
            }
            "Print Response Headers" => {
                let headers_str = headers
                    .iter()
                    .map(|(k, v)| format!("    {}: {}", k, v.to_str().unwrap_or("<binary>")))
                    .collect::<Vec<_>>()
                    .join("\n");
                let _ = emit_status(
                    py,
                    callback_obj,
                    &format!("  > Action: Response Headers:\n {}", headers_str),
                );
            }
            "Print Response Content (Text)" => {
                if content.is_none() {
                    // This is slightly inefficient as it consumes the whole response even if not needed by other actions,
                    // but it's simpler. We use a trick: run_actions is called once per request.
                    // Actually, we SHOULD buffer it here if we want multiple actions.
                    // Since Response is consumed by .bytes(), we must do it once.
                }
                // Wait, if we use blocking::Response, bytes() consumes it.
                // Let's just consume it now if we need it for any action.
                // Re-implementation logic:
            }
            _ => {}
        }
    }

    // Better implementation:
    // Check if any action needs body.
    let needs_body = actions.iter().any(|a| {
        let t = a.get("type").and_then(|v| v.as_str()).unwrap_or("");
        t == "Print Response Content (Text)" || t == "Save Response Content (Binary)"
    });

    if needs_body {
        let bytes = response
            .bytes()
            .context("Failed to read response body")?
            .to_vec();
        content = Some(bytes);
    }

    for action in actions {
        let action_type = action.get("type").and_then(|v| v.as_str()).unwrap_or("");
        let param = action.get("param").and_then(|v| v.as_str()).unwrap_or("");

        match action_type {
            "Print Response Content (Text)" => {
                if let Some(ref data) = content {
                    let text = String::from_utf8_lossy(data);
                    let _ = emit_status(
                        py,
                        callback_obj,
                        &format!("  > Action: Response Content:\n {}", text.trim()),
                    );
                }
            }
            "Save Response Content (Binary)" => {
                if let Some(ref data) = content {
                    if param.is_empty() {
                        let _ = emit_error(
                            py,
                            callback_obj,
                            "  > Action: Save failed. No file path provided in parameter.",
                        );
                        continue;
                    }

                    let mut filepath = Path::new(param).to_path_buf();
                    if filepath.is_dir() {
                        let filename = url
                            .split('/')
                            .last()
                            .and_then(|s| s.split('?').next())
                            .unwrap_or("response.dat");
                        filepath = filepath.join(filename);
                    }

                    if let Some(parent) = filepath.parent() {
                        fs::create_dir_all(parent).context("Failed to create directories")?;
                    }
                    fs::write(&filepath, data).context("Failed to write file")?;
                    let _ = emit_status(
                        py,
                        callback_obj,
                        &format!("  > Action: Response content saved to {:?}", filepath),
                    );
                }
            }
            _ => {}
        }
    }

    Ok(())
}
