use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::command;
use tokio::fs;

// ── Normalised types returned to the frontend ─────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BenchmarkTime {
    pub avg_sec: f64,
    pub min_sec: f64,
    pub max_sec: f64,
    pub total_sec: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BenchmarkMemory {
    pub avg_peak_mb: f64,
    pub max_peak_mb: f64,
    pub avg_delta_mb: f64,
    pub max_leaked_mb: f64,
}

/// One benchmark entry from a general-purpose suite (thumbnails, database, ML models).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeneralBenchmark {
    pub name: String,
    pub iterations: u32,
    pub time: BenchmarkTime,
    pub memory: BenchmarkMemory,
}

/// CV quality metrics for a single ASP output image.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspMetrics {
    pub sharpness: f64,
    pub coverage: f64,
    pub seam_gradient: f64,
    pub color_entropy: f64,
    pub ghosting_score: f64,
    pub ghosting_siqe: Option<f64>,
    pub seam_coherence: f64,
    pub seam_visibility: Option<f64>,
    pub strip_banding_score: Option<f64>,
    pub ghost_seam_max: Option<f64>,
    pub ghost_seam_scores: Option<Vec<f64>>,
    pub seam_color_min: Option<f64>,
    pub seam_color_scores: Option<Vec<f64>>,
    pub seam_ncc_min: Option<f64>,
    pub seam_ncc_scores: Option<Vec<f64>>,
    pub composite_quality: Option<f64>,
    pub width: Option<u32>,
    pub height: Option<u32>,
    pub rlhf_score: Option<f64>,
    pub rlhf_flagged: Option<bool>,
    pub rlhf_uncertainty: Option<f64>,
    pub rlhf_needs_review: Option<bool>,
}

/// Per-frame alignment data from the ASP alignment block.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspAffineEntry {
    pub frame: u32,
    pub tx: f64,
    pub ty: f64,
    pub a: f64,
    pub b: f64,
}

/// Alignment block from the ASP result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspAlignment {
    pub affines: Vec<AspAffineEntry>,
    pub dy_steps: Vec<f64>,
    pub dx_steps: Vec<f64>,
    pub dy_cv: f64,
    pub dx_cv: f64,
}

/// Photometric correction block.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspPhotometric {
    pub ref_lum: Option<f64>,
    pub bg_lums: Vec<Option<f64>>,
    pub applied_gains: Vec<f64>,
    pub frames_corrected: u32,
    pub gain_range: Vec<f64>,
}

/// Affine validation health block.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspAffineHealth {
    pub valid: bool,
    pub ratio: f64,
    pub min_gap_px: f64,
    pub max_rotation: f64,
    pub max_scale_dev: f64,
    pub reason: String,
}

/// Frame selection telemetry block.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspFrameSelection {
    pub original_count: u32,
    pub smart_select_count: u32,
    pub spatial_dedup_count: u32,
    pub final_count: u32,
    pub frames_dropped_smart: u32,
    pub frames_dropped_dedup: u32,
    pub selection_mode: String,
}

/// Per-stage timing breakdown for an ASP run.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspTiming {
    pub simple_stitch_sec: Option<f64>,
    pub birefnet_sec: Option<f64>,
    pub matching_sec: Option<f64>,
    pub bundle_adjust_sec: Option<f64>,
    pub ecc_sec: Option<f64>,
    pub render_sec: Option<f64>,
    pub composite_sec: Option<f64>,
    pub visualisations_sec: Option<f64>,
    pub total_sec: f64,
}

/// Ground truth comparison for one dataset.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GroundTruthMetrics {
    pub ssim_vs_gt: Option<f64>,
    pub aligned_ssim_vs_gt: Option<f64>,
    pub psnr_vs_gt: Option<f64>,
    pub verdict: Option<String>,
}

/// One dataset result inside an ASP benchmark report.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspDataset {
    pub name: String,
    pub used_fallback: bool,
    pub fallback_reason: Option<String>,
    pub time: AspTiming,
    pub frame_count: Option<u32>,
    pub canvas_width: Option<u32>,
    pub canvas_height: Option<u32>,
    pub metrics_asp: Option<AspMetrics>,
    pub metrics_simple: Option<AspMetrics>,
    pub comparison: Option<serde_json::Value>,
    pub ground_truth: Option<GroundTruthMetrics>,
    pub matching: Option<serde_json::Value>,
    pub alignment: Option<AspAlignment>,
    pub photometric: Option<AspPhotometric>,
    pub affine_health: Option<AspAffineHealth>,
    pub frame_selection: Option<AspFrameSelection>,
    pub pipeline_config: Option<serde_json::Value>,
}

/// Top-level summary block from an ASP report.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AspSummary {
    pub total_datasets: u32,
    pub datasets_passed: u32,
    pub datasets_fallback: u32,
    pub total_time_sec: f64,
    pub avg_time_per_dataset_sec: f64,
    pub avg_sharpness_asp: Option<f64>,
    pub avg_sharpness_simple: Option<f64>,
    pub avg_ghosting_asp: Option<f64>,
    pub avg_coverage_asp: Option<f64>,
    pub verdict_counts: Option<serde_json::Value>,
}

/// Top-level summary block from a general benchmark report.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GeneralSummary {
    pub total_execution_time_sec: f64,
    pub max_peak_memory_mb: f64,
    pub benchmarks_passed: u32,
    pub performance_insights: Option<serde_json::Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemInfo {
    pub timestamp: String,
    pub platform: String,
    pub python: Option<String>,
    pub cpu: String,
    pub cpu_threads: Option<u32>,
    pub ram_gb: Option<f64>,
    pub gpu: Option<String>,
    pub cuda_version: Option<String>,
    pub vram_gb: Option<f64>,
}

/// Discriminated union: a report is either ASP-style or general-suite-style.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "kind")]
pub enum BenchmarkReport {
    Asp {
        file_name: String,
        system: SystemInfo,
        summary: AspSummary,
        datasets: Vec<AspDataset>,
    },
    General {
        file_name: String,
        suite_name: String,
        system: SystemInfo,
        summary: GeneralSummary,
        benchmarks: Vec<GeneralBenchmark>,
    },
}

// ── JSON deserialization helpers ───────────────────────────────────────────────

fn extract_system(v: &serde_json::Value) -> SystemInfo {
    let s = v;
    SystemInfo {
        timestamp: s["timestamp"].as_str().unwrap_or("").to_string(),
        platform: s["platform"].as_str().unwrap_or("Unknown").to_string(),
        python: s["python"].as_str().map(str::to_string),
        cpu: s["cpu"].as_str().unwrap_or("Unknown").to_string(),
        cpu_threads: s["cpu_threads"].as_u64().map(|v| v as u32),
        ram_gb: s["ram_gb"].as_f64(),
        gpu: s["gpu"].as_str().map(str::to_string),
        cuda_version: s["cuda_version"].as_str().map(str::to_string),
        vram_gb: s["vram_gb"].as_f64(),
    }
}

fn extract_f64_array(v: &serde_json::Value) -> Option<Vec<f64>> {
    v.as_array().map(|arr| arr.iter().filter_map(|x| x.as_f64()).collect())
}

fn extract_asp_metrics(v: &serde_json::Value) -> Option<AspMetrics> {
    if v.is_null() || !v.is_object() {
        return None;
    }
    Some(AspMetrics {
        sharpness: v["sharpness"].as_f64().unwrap_or(0.0),
        coverage: v["coverage"].as_f64().unwrap_or(0.0),
        seam_gradient: v["seam_gradient"].as_f64().unwrap_or(0.0),
        color_entropy: v["color_entropy"].as_f64().unwrap_or(0.0),
        ghosting_score: v["ghosting_score"].as_f64().unwrap_or(0.0),
        ghosting_siqe: v["ghosting_siqe"].as_f64(),
        seam_coherence: v["seam_coherence"].as_f64().unwrap_or(0.0),
        seam_visibility: v["seam_visibility"].as_f64(),
        strip_banding_score: v["strip_banding_score"].as_f64(),
        ghost_seam_max: v["ghost_seam_max"].as_f64(),
        ghost_seam_scores: extract_f64_array(&v["ghost_seam_scores"]),
        seam_color_min: v["seam_color_min"].as_f64(),
        seam_color_scores: extract_f64_array(&v["seam_color_scores"]),
        seam_ncc_min: v["seam_ncc_min"].as_f64(),
        seam_ncc_scores: extract_f64_array(&v["seam_ncc_scores"]),
        composite_quality: v["composite_quality"].as_f64(),
        width: v["width"].as_u64().map(|x| x as u32),
        height: v["height"].as_u64().map(|x| x as u32),
        rlhf_score: v["rlhf_score"].as_f64(),
        rlhf_flagged: v["rlhf_flagged"].as_bool(),
        rlhf_uncertainty: v["rlhf_uncertainty"].as_f64(),
        rlhf_needs_review: v["rlhf_needs_review"].as_bool(),
    })
}

fn extract_alignment(v: &serde_json::Value) -> Option<AspAlignment> {
    if v.is_null() || !v.is_object() {
        return None;
    }
    let affines = v["affines"].as_array().map(|arr| {
        arr.iter().map(|a| AspAffineEntry {
            frame: a["frame"].as_u64().unwrap_or(0) as u32,
            tx: a["tx"].as_f64().unwrap_or(0.0),
            ty: a["ty"].as_f64().unwrap_or(0.0),
            a: a["a"].as_f64().unwrap_or(1.0),
            b: a["b"].as_f64().unwrap_or(0.0),
        }).collect()
    }).unwrap_or_default();
    Some(AspAlignment {
        affines,
        dy_steps: extract_f64_array(&v["dy_steps"]).unwrap_or_default(),
        dx_steps: extract_f64_array(&v["dx_steps"]).unwrap_or_default(),
        dy_cv: v["dy_cv"].as_f64().unwrap_or(0.0),
        dx_cv: v["dx_cv"].as_f64().unwrap_or(0.0),
    })
}

fn extract_photometric(v: &serde_json::Value) -> Option<AspPhotometric> {
    if v.is_null() || !v.is_object() {
        return None;
    }
    let bg_lums = v["bg_lums"].as_array().map(|arr| {
        arr.iter().map(|x| if x.is_null() { None } else { x.as_f64() }).collect()
    }).unwrap_or_default();
    Some(AspPhotometric {
        ref_lum: v["ref_lum"].as_f64(),
        bg_lums,
        applied_gains: extract_f64_array(&v["applied_gains"]).unwrap_or_default(),
        frames_corrected: v["frames_corrected"].as_u64().unwrap_or(0) as u32,
        gain_range: extract_f64_array(&v["gain_range"]).unwrap_or_default(),
    })
}

fn extract_affine_health(v: &serde_json::Value) -> Option<AspAffineHealth> {
    if v.is_null() || !v.is_object() {
        return None;
    }
    Some(AspAffineHealth {
        valid: v["valid"].as_bool().unwrap_or(false),
        ratio: v["ratio"].as_f64().unwrap_or(0.0),
        min_gap_px: v["min_gap_px"].as_f64().unwrap_or(0.0),
        max_rotation: v["max_rotation"].as_f64().unwrap_or(0.0),
        max_scale_dev: v["max_scale_dev"].as_f64().unwrap_or(0.0),
        reason: v["reason"].as_str().unwrap_or("").to_string(),
    })
}

fn extract_frame_selection(v: &serde_json::Value) -> Option<AspFrameSelection> {
    if v.is_null() || !v.is_object() {
        return None;
    }
    Some(AspFrameSelection {
        original_count: v["original_count"].as_u64().unwrap_or(0) as u32,
        smart_select_count: v["smart_select_count"].as_u64().unwrap_or(0) as u32,
        spatial_dedup_count: v["spatial_dedup_count"].as_u64().unwrap_or(0) as u32,
        final_count: v["final_count"].as_u64().unwrap_or(0) as u32,
        frames_dropped_smart: v["frames_dropped_smart"].as_u64().unwrap_or(0) as u32,
        frames_dropped_dedup: v["frames_dropped_dedup"].as_u64().unwrap_or(0) as u32,
        selection_mode: v["selection_mode"].as_str().unwrap_or("phase_correlation").to_string(),
    })
}

fn extract_asp_timing(v: &serde_json::Value) -> AspTiming {
    AspTiming {
        simple_stitch_sec: v["simple_stitch_sec"].as_f64(),
        birefnet_sec: v["birefnet_sec"].as_f64(),
        matching_sec: v["matching_sec"].as_f64(),
        bundle_adjust_sec: v["bundle_adjust_sec"].as_f64(),
        ecc_sec: v["ecc_sec"].as_f64(),
        render_sec: v["render_sec"].as_f64(),
        composite_sec: v["composite_sec"].as_f64(),
        visualisations_sec: v["visualisations_sec"].as_f64(),
        total_sec: v["total_sec"].as_f64().unwrap_or(0.0),
    }
}

fn extract_ground_truth(v: &serde_json::Value) -> Option<GroundTruthMetrics> {
    if v.is_null() || !v.is_object() {
        return None;
    }
    Some(GroundTruthMetrics {
        ssim_vs_gt: v["ssim_vs_gt"].as_f64(),
        aligned_ssim_vs_gt: v["aligned_ssim_vs_gt"].as_f64(),
        psnr_vs_gt: v["psnr_vs_gt"].as_f64(),
        verdict: v["verdict"].as_str().map(str::to_string),
    })
}

fn parse_asp_report(
    file_name: String,
    v: serde_json::Value,
) -> Option<BenchmarkReport> {
    let system = extract_system(&v["system"]);
    let s = &v["summary"];

    let summary = AspSummary {
        total_datasets: s["total_datasets"].as_u64().unwrap_or(0) as u32,
        datasets_passed: s["datasets_passed"].as_u64().unwrap_or(0) as u32,
        datasets_fallback: s["datasets_fallback"].as_u64().unwrap_or(0) as u32,
        total_time_sec: s["total_time_sec"].as_f64().unwrap_or(0.0),
        avg_time_per_dataset_sec: s["avg_time_per_dataset_sec"].as_f64().unwrap_or(0.0),
        avg_sharpness_asp: s["avg_sharpness_asp"].as_f64(),
        avg_sharpness_simple: s["avg_sharpness_simple"].as_f64(),
        avg_ghosting_asp: s["avg_ghosting_asp"].as_f64(),
        avg_coverage_asp: s["avg_coverage_asp"].as_f64(),
        verdict_counts: Some(s["verdict_counts"].clone()),
    };

    let datasets = v["datasets"]
        .as_array()
        .map(|arr| {
            arr.iter()
                .map(|d| {
                    let gt_data = &d["ground_truth"];
                    let gt_metrics = if gt_data.is_object() {
                        extract_ground_truth(gt_data)
                    } else {
                        // Try extracting from comparison.gt_verdict + nested
                        let comp = &d["comparison"];
                        if comp["gt_verdict"].is_string() {
                            Some(GroundTruthMetrics {
                                ssim_vs_gt: None,
                                aligned_ssim_vs_gt: None,
                                psnr_vs_gt: None,
                                verdict: comp["gt_verdict"].as_str().map(str::to_string),
                            })
                        } else {
                            None
                        }
                    };

                    AspDataset {
                        name: d["name"].as_str().unwrap_or("unknown").to_string(),
                        used_fallback: d["used_fallback"].as_bool().unwrap_or(false),
                        fallback_reason: d["fallback_reason"].as_str().map(str::to_string),
                        time: extract_asp_timing(&d["time"]),
                        frame_count: d["frames"]["count"]
                            .as_u64()
                            .map(|x| x as u32),
                        canvas_width: d["canvas"]["width"].as_u64().map(|x| x as u32),
                        canvas_height: d["canvas"]["height"].as_u64().map(|x| x as u32),
                        metrics_asp: extract_asp_metrics(&d["metrics_asp"]),
                        metrics_simple: extract_asp_metrics(&d["metrics_simple"]),
                        comparison: Some(d["comparison"].clone()),
                        ground_truth: gt_metrics,
                        matching: Some(d["matching"].clone()),
                        alignment: extract_alignment(&d["alignment"]),
                        photometric: extract_photometric(&d["photometric"]),
                        affine_health: extract_affine_health(&d["affine_health"]),
                        frame_selection: extract_frame_selection(&d["frame_selection"]),
                        pipeline_config: if d["pipeline_config"].is_object() {
                            Some(d["pipeline_config"].clone())
                        } else {
                            None
                        },
                    }
                })
                .collect()
        })
        .unwrap_or_default();

    Some(BenchmarkReport::Asp {
        file_name,
        system,
        summary,
        datasets,
    })
}

fn parse_general_report(
    file_name: String,
    v: serde_json::Value,
) -> Option<BenchmarkReport> {
    let suite_name = v["metadata"]["suite_name"]
        .as_str()
        .or_else(|| v["suite"].as_str())
        .unwrap_or("Unknown Suite")
        .to_string();

    let system = extract_system(&v["system"]);

    let benchmarks_raw = v["benchmarks"]
        .as_array()
        .or_else(|| v["results"].as_array())
        .cloned()
        .unwrap_or_default();

    let benchmarks: Vec<GeneralBenchmark> = benchmarks_raw
        .iter()
        .filter_map(|b| {
            let t = &b["time"];
            let m = &b["memory"];
            Some(GeneralBenchmark {
                name: b["name"].as_str()?.to_string(),
                iterations: b["iterations"].as_u64().unwrap_or(1) as u32,
                time: BenchmarkTime {
                    avg_sec: t["avg_sec"].as_f64().unwrap_or(0.0),
                    min_sec: t["min_sec"].as_f64().unwrap_or(0.0),
                    max_sec: t["max_sec"].as_f64().unwrap_or(0.0),
                    total_sec: t["total_sec"].as_f64().unwrap_or(0.0),
                },
                memory: BenchmarkMemory {
                    avg_peak_mb: m["avg_peak_mb"].as_f64().unwrap_or(0.0),
                    max_peak_mb: m["max_peak_mb"].as_f64().unwrap_or(0.0),
                    avg_delta_mb: m["avg_delta_mb"].as_f64().unwrap_or(0.0),
                    max_leaked_mb: m["max_leaked_mb"].as_f64().unwrap_or(0.0),
                },
            })
        })
        .collect();

    let s = &v["summary"];
    let total_time = s["total_execution_time_sec"]
        .as_f64()
        .or_else(|| s["total_time_sec"].as_f64())
        .unwrap_or(0.0);

    let summary = GeneralSummary {
        total_execution_time_sec: total_time,
        max_peak_memory_mb: s["max_peak_memory_mb"].as_f64().unwrap_or(0.0),
        benchmarks_passed: s["benchmarks_passed"].as_u64().unwrap_or(0) as u32,
        performance_insights: v.get("performance_insights").cloned(),
    };

    Some(BenchmarkReport::General {
        file_name,
        suite_name,
        system,
        summary,
        benchmarks,
    })
}

// ── Tauri commands ────────────────────────────────────────────────────────────

/// Load all benchmark JSON reports from the results directory.
///
/// Returns at most `limit` reports (most-recently-modified first).
/// Silently skips files that fail to parse — the dashboard shows whatever
/// it can decode rather than erroring on one bad file.
#[command]
pub async fn load_benchmark_reports(
    results_dir: Option<String>,
    limit: Option<usize>,
) -> Result<Vec<BenchmarkReport>, String> {
    let dir: PathBuf = if let Some(d) = results_dir {
        PathBuf::from(d)
    } else {
        // Default: relative to the repo root from the Tauri binary location.
        // In dev mode the CWD is typically the frontend/ directory.
        let mut p = std::env::current_dir().map_err(|e| e.to_string())?;
        // Walk up until we find backend/benchmark/results or hit the FS root.
        loop {
            let candidate = p.join("backend").join("benchmark").join("results");
            if candidate.exists() {
                p = candidate;
                break;
            }
            if !p.pop() {
                return Err("Could not locate backend/benchmark/results directory".into());
            }
        }
        p
    };

    let mut entries = tokio::fs::read_dir(&dir)
        .await
        .map_err(|e| format!("Cannot read {}: {}", dir.display(), e))?;

    let mut files: Vec<(std::time::SystemTime, PathBuf)> = Vec::new();
    while let Ok(Some(entry)) = entries.next_entry().await {
        let path = entry.path();
        if path.extension().and_then(|e| e.to_str()) != Some("json") {
            continue;
        }
        let mtime = entry
            .metadata()
            .await
            .ok()
            .and_then(|m| m.modified().ok())
            .unwrap_or(std::time::UNIX_EPOCH);
        files.push((mtime, path));
    }

    // Most-recent first.
    files.sort_by(|a, b| b.0.cmp(&a.0));

    let cap = limit.unwrap_or(usize::MAX);
    let mut reports: Vec<BenchmarkReport> = Vec::new();

    for (_mtime, path) in files.into_iter().take(cap) {
        let file_name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("unknown.json")
            .to_string();

        let content = match fs::read_to_string(&path).await {
            Ok(c) => c,
            Err(_) => continue,
        };

        let v: serde_json::Value = match serde_json::from_str(&content) {
            Ok(v) => v,
            Err(_) => continue,
        };

        // Discriminate by presence of the "datasets" key (ASP) vs "benchmarks"/"results" (general).
        let report = if v.get("datasets").and_then(|d| d.as_array()).is_some() {
            parse_asp_report(file_name, v)
        } else {
            parse_general_report(file_name, v)
        };

        if let Some(r) = report {
            reports.push(r);
        }
    }

    Ok(reports)
}
