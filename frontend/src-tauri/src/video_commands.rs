use serde::{Deserialize, Serialize};
use std::path::Path;
use tauri::Manager;

#[derive(Serialize, Deserialize, Clone)]
pub struct VideoExtractionParams {
    pub video_path: String,
    pub start_ms: i64,
    pub end_ms: i64,
    pub output_path: String,
    pub target_width: Option<u32>,
    pub target_height: Option<u32>,
    pub mute_audio: bool,
    pub use_ffmpeg: bool,
    pub speed: f64,
}

#[derive(Serialize, Clone)]
pub struct VideoExtractionProgress {
    pub task_id: String,
    pub progress: u32,
    pub message: String,
    pub status: String,
}

/// Extract a video clip using FFmpeg
#[tauri::command]
pub async fn extract_video_clip(
    app: tauri::AppHandle,
    params: VideoExtractionParams,
    task_id: String,
) -> Result<String, String> {
    // Emit progress event
    let _ = app.emit(
        "task-progress",
        VideoExtractionProgress {
            task_id: task_id.clone(),
            progress: 0,
            message: "Starting video extraction...".to_string(),
            status: "running".to_string(),
        },
    );

    if params.use_ffmpeg {
        extract_with_ffmpeg(app, params, task_id).await
    } else {
        extract_with_python(app, params, task_id).await
    }
}

async fn extract_with_ffmpeg(
    app: tauri::AppHandle,
    params: VideoExtractionParams,
    task_id: String,
) -> Result<String, String> {
    use std::process::Command;

    let t_start = params.start_ms as f64 / 1000.0;
    let t_end = params.end_ms as f64 / 1000.0;
    let duration = t_end - t_start;

    let mut cmd = Command::new("ffmpeg");
    cmd.args(&[
        "-y",
        "-ss",
        &t_start.to_string(),
        "-t",
        &duration.to_string(),
    ]);
    cmd.args(&["-i", &params.video_path]);

    // Video filters
    let mut filters = Vec::new();

    // Scaling
    if let (Some(w), Some(h)) = (params.target_width, params.target_height) {
        filters.push(format!("scale={}:{}", w, h));
    }

    // Speed adjustment
    if (params.speed - 1.0).abs() > 0.001 {
        let pts_mult = 1.0 / params.speed;
        filters.push(format!("setpts={}*PTS", pts_mult));
    }

    if !filters.is_empty() {
        cmd.args(&["-vf", &filters.join(",")]);
    }

    // Codec settings
    cmd.args(&["-c:v", "libx264", "-movflags", "+faststart"]);

    // Audio handling
    if params.mute_audio {
        cmd.arg("-an");
    } else {
        // Audio speed adjustment using atempo
        let mut audio_filters = Vec::new();
        let mut s = params.speed;

        // atempo is limited to [0.5, 2.0], so chain filters if needed
        while s > 2.0 {
            audio_filters.push("atempo=2.0".to_string());
            s /= 2.0;
        }
        while s < 0.5 {
            audio_filters.push("atempo=0.5".to_string());
            s /= 0.5;
        }
        if (s - 1.0).abs() > 0.001 {
            audio_filters.push(format!("atempo={}", s));
        }

        if !audio_filters.is_empty() {
            cmd.args(&["-af", &audio_filters.join(",")]);
        }

        cmd.args(&["-c:a", "aac", "-b:a", "128k"]);
    }

    cmd.arg(&params.output_path);

    // Emit progress
    let _ = app.emit(
        "task-progress",
        VideoExtractionProgress {
            task_id: task_id.clone(),
            progress: 30,
            message: "Running FFmpeg...".to_string(),
            status: "running".to_string(),
        },
    );

    // Execute command
    let output = cmd.output().map_err(|e| format!("FFmpeg error: {}", e))?;

    if output.status.success() {
        let _ = app.emit(
            "task-complete",
            serde_json::json!({
                "taskId": task_id,
                "success": true,
                "message": "Video extraction completed"
            }),
        );
        Ok(params.output_path)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("FFmpeg failed: {}", error))
    }
}

async fn extract_with_python(
    app: tauri::AppHandle,
    params: VideoExtractionParams,
    task_id: String,
) -> Result<String, String> {
    use std::process::Command;

    // Build Python script to call MoviePy
    let python_script = format!(
        r#"
import sys
sys.path.insert(0, '../../')
from gui.src.helpers.video.video_extractor_worker import VideoExtractionWorker

worker = VideoExtractionWorker(
    video_path="{}",
    start_ms={},
    end_ms={},
    output_path="{}",
    target_size={},
    mute_audio={},
    use_ffmpeg=False,
    speed={}
)

try:
    worker.run()
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {{e}}")
    sys.exit(1)
"#,
        params.video_path,
        params.start_ms,
        params.end_ms,
        params.output_path,
        match (params.target_width, params.target_height) {
            (Some(w), Some(h)) => format!("({}, {})", w, h),
            _ => "None".to_string(),
        },
        params.mute_audio,
        params.speed
    );

    let _ = app.emit(
        "task-progress",
        VideoExtractionProgress {
            task_id: task_id.clone(),
            progress: 30,
            message: "Running MoviePy extraction...".to_string(),
            status: "running".to_string(),
        },
    );

    let output = Command::new("python")
        .arg("-c")
        .arg(&python_script)
        .output()
        .map_err(|e| format!("Failed to run Python: {}", e))?;

    if output.status.success() {
        let _ = app.emit(
            "task-complete",
            serde_json::json!({
                "taskId": task_id,
                "success": true,
                "message": "Video extraction completed"
            }),
        );
        Ok(params.output_path)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("Python extraction failed: {}", error))
    }
}

/// Extract frames from video at specific intervals
#[tauri::command]
pub async fn extract_video_frames(
    app: tauri::AppHandle,
    video_path: String,
    output_dir: String,
    interval_ms: i64,
    task_id: String,
) -> Result<Vec<String>, String> {
    // Use the Rust-based frame extraction from the base crate
    let _ = app.emit(
        "task-progress",
        VideoExtractionProgress {
            task_id: task_id.clone(),
            progress: 0,
            message: "Starting frame extraction...".to_string(),
            status: "running".to_string(),
        },
    );

    // Call Python backend with base module
    let python_script = format!(
        r#"
import sys
import json
sys.path.insert(0, '../../')
import base

frames = base.extract_video_frames("{}", "{}", {})
print(json.dumps({{"frames": frames}}))
"#,
        video_path, output_dir, interval_ms
    );

    let output = std::process::Command::new("python")
        .arg("-c")
        .arg(&python_script)
        .output()
        .map_err(|e| format!("Failed to run Python: {}", e))?;

    if output.status.success() {
        let result_str = String::from_utf8_lossy(&output.stdout);
        let result: serde_json::Value = serde_json::from_str(&result_str)
            .map_err(|e| format!("Failed to parse result: {}", e))?;

        let frames = result["frames"]
            .as_array()
            .ok_or("Invalid frames data")?
            .iter()
            .filter_map(|v| v.as_str().map(String::from))
            .collect();

        let _ = app.emit(
            "task-complete",
            serde_json::json!({
                "taskId": task_id,
                "success": true,
                "message": "Frame extraction completed"
            }),
        );

        Ok(frames)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("Frame extraction failed: {}", error))
    }
}

/// Get video metadata (duration, dimensions, codec)
#[tauri::command]
pub fn get_video_metadata(video_path: String) -> Result<serde_json::Value, String> {
    use std::process::Command;

    let output = Command::new("ffprobe")
        .args(&[
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            &video_path,
        ])
        .output()
        .map_err(|e| format!("FFprobe error: {}", e))?;

    if output.status.success() {
        let result_str = String::from_utf8_lossy(&output.stdout);
        let metadata: serde_json::Value = serde_json::from_str(&result_str)
            .map_err(|e| format!("Failed to parse metadata: {}", e))?;
        Ok(metadata)
    } else {
        let error = String::from_utf8_lossy(&output.stderr);
        Err(format!("Failed to get video metadata: {}", error))
    }
}
