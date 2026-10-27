// Convert pilot view (#894) plus directory batch (#1107).
// Injected HostClient instance (provided by the shell). No global declare.

import { open } from "@tauri-apps/plugin-dialog";
import React, { useRef, useState } from "react";
import type { ConvertBatchParams, JobStatus } from "../../../contracts/generated/ts";
import type { HostClient } from "../hostclient";

export interface ConvertPilotProps {
  hostClient: HostClient;
}

const OUTPUT_FORMATS = ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "ico", "gif"] as const;
const INPUT_FORMATS = ["webp", "avif", "png", "jpg", "jpeg", "bmp", "gif", "tiff"] as const;
const ALGORITHMS = ["lanczos", "bicubic", "bilinear", "nearest"] as const;
const VIDEO_CODECS = ["h264", "hevc", "av1", "vp9", "copy"] as const;
const AUDIO_CODECS = ["aac", "opus", "mp3", "flac", "copy"] as const;

type OutputFormat = (typeof OUTPUT_FORMATS)[number];
type InputFormat = (typeof INPUT_FORMATS)[number];
type BatchAction = "convert" | "resample" | "reencode";

function isOutputFormat(value: string): value is OutputFormat {
  return (OUTPUT_FORMATS as readonly string[]).includes(value);
}

function extensionOf(path: string): string | undefined {
  const name = path.split(/[/\\]/).pop() ?? "";
  const dot = name.lastIndexOf(".");
  if (dot <= 0 || dot === name.length - 1) {
    return undefined;
  }
  return name.slice(dot + 1).toLowerCase();
}

export function ConvertPilot({ hostClient }: ConvertPilotProps) {
  const [inputPath, setInputPath] = useState("");
  const [outputPath, setOutputPath] = useState("");
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("png");
  const [status, setStatus] = useState("ready");
  const [directory, setDirectory] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [files, setFiles] = useState<string[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [progress, setProgress] = useState({ done: 0, total: 0 });
  const [resampleWidth, setResampleWidth] = useState(64);
  const [resampleHeight, setResampleHeight] = useState(64);
  const [algorithm, setAlgorithm] = useState<(typeof ALGORITHMS)[number]>("lanczos");
  const [keepOriginalFormat, setKeepOriginalFormat] = useState(true);
  const [videoCodec, setVideoCodec] = useState<(typeof VIDEO_CODECS)[number]>("h264");
  const [audioCodec, setAudioCodec] = useState<(typeof AUDIO_CODECS)[number]>("aac");
  const [crf, setCrf] = useState(28);
  const [recursive, setRecursive] = useState(false);
  const [inputFormats, setInputFormats] = useState<readonly InputFormat[]>([]);
  const jobRef = useRef("");

  const onOutputPath = (value: string) => {
    setOutputPath(value);
    const extension = extensionOf(value);
    if (extension && isOutputFormat(extension)) {
      setOutputFormat(extension);
    }
  };

  const onConvert = async () => {
    const extension = extensionOf(outputPath);
    let format: OutputFormat = outputFormat;
    let destination = outputPath;
    if (extension) {
      if (!isOutputFormat(extension)) {
        setStatus(`failed: unsupported output extension .${extension}`);
        return;
      }
      format = extension;
    } else if (destination) {
      destination = `${destination}.${outputFormat}`;
    }
    setStatus("calling");
    try {
      const result = await hostClient.convert({
        input_path: inputPath,
        output_path: destination,
        output_format: format,
        quality: 95,
      });
      setStatus(result.success ? "ok" : `failed: ${result.error ?? "unknown"}`);
    } catch (err) {
      setStatus(`error: ${String(err)}`);
    }
  };

  const browseInto = async (apply: (path: string) => void) => {
    const picked = await open({ directory: true, multiple: false });
    if (typeof picked === "string") {
      apply(picked);
    }
  };

  const browseFile = async (apply: (path: string) => void) => {
    const picked = await open({ directory: false, multiple: false });
    if (typeof picked === "string") {
      apply(picked);
    }
  };

  const onList = async () => {
    setStatus("listing");
    try {
      const listed = await hostClient.convertListDir({ directory });
      setFiles(listed.files);
      setSelectedFiles(listed.files);
      setStatus(listed.error ? `list: ${listed.error}` : `listed ${listed.files.length}`);
    } catch (err) {
      setFiles([]);
      setSelectedFiles([]);
      setStatus(`error: ${String(err)}`);
    }
  };

  const visibleFiles =
    inputFormats.length === 0
      ? files
      : files.filter((file) => {
          const dot = file.lastIndexOf(".");
          if (dot < 0) {
            return false;
          }
          return (inputFormats as readonly string[]).includes(file.slice(dot + 1).toLowerCase());
        });

  const toggleFile = (file: string) => {
    setSelectedFiles((current) =>
      current.includes(file) ? current.filter((item) => item !== file) : [...current, file],
    );
  };

  const onCancelBatch = async () => {
    const jobId = jobRef.current;
    if (!jobId) {
      return;
    }
    try {
      await hostClient.cancelJob(jobId);
      setStatus("cancelled");
    } catch (err) {
      setStatus(`error: ${String(err)}`);
    }
  };

  const finishBatch = async (params: ConvertBatchParams, total: number) => {
    setStatus("batch");
    setProgress({ done: 0, total });
    try {
      const started = await hostClient.convertBatch(params);
      jobRef.current = started.job_id;
      const finished = await pollJob(hostClient, started.job_id, setProgress);
      if (finished.state === "cancelled") {
        setStatus("cancelled");
      } else if (finished.state === "failed") {
        setStatus("failed: batch");
      } else if (finished.state === "completed") {
        setStatus(completedBatchStatus(finished.result));
      } else {
        setStatus(finished.state);
      }
    } catch (err) {
      setStatus(`error: ${String(err)}`);
    }
  };

  const onBatch = async (action: BatchAction) => {
    const chosen = visibleFiles.filter((file) => selectedFiles.includes(file));
    if (!directory || !outputDir) {
      setStatus("failed: directory and output directory are required");
      return;
    }
    if (chosen.length === 0) {
      setStatus("failed: no files selected");
      return;
    }
    const params: ConvertBatchParams = {
      input_dir: directory,
      output_dir: outputDir,
      ...(action === "resample" && keepOriginalFormat ? {} : { output_format: outputFormat }),
      paths: chosen,
      action,
      quality: 95,
      overwrite: true,
      ...(action === "resample" ? { width: resampleWidth, height: resampleHeight, algorithm } : {}),
      ...(action === "reencode" ? { video_codec: videoCodec, audio_codec: audioCodec, crf } : {}),
    };
    await finishBatch(params, chosen.length);
  };

  const toggleInputFormat = (format: InputFormat) => {
    setInputFormats((current) =>
      current.includes(format) ? current.filter((item) => item !== format) : [...current, format],
    );
  };

  const onConvertDirectory = async () => {
    if (!directory || !outputDir) {
      setStatus("failed: directory and output directory are required");
      return;
    }
    const formats = INPUT_FORMATS.filter((format) => inputFormats.includes(format));
    const params: ConvertBatchParams = {
      input_dir: directory,
      output_dir: outputDir,
      output_format: outputFormat,
      quality: 95,
      overwrite: true,
      action: "convert",
      recursive,
      ...(formats.length > 0 ? { input_formats: [...formats] } : {}),
    };
    await finishBatch(params, 0);
  };

  return (
    <div data-testid="convert-pilot">
      <h1>Convert</h1>
      <p>Calls convert.convert via the injected HostClient.</p>
      <label>
        Input path{" "}
        <input value={inputPath} onChange={(e) => setInputPath(e.target.value)} />
      </label>
      <button type="button" onClick={() => void browseFile(setInputPath)}>
        Browse input file
      </button>
      <label>
        Output path{" "}
        <input value={outputPath} onChange={(e) => onOutputPath(e.target.value)} />
      </label>
      <button type="button" onClick={() => void browseFile(onOutputPath)}>
        Browse output file
      </button>
      <label>
        Format{" "}
        <select value={outputFormat} onChange={(e) => setOutputFormat(e.target.value as OutputFormat)}>
          {OUTPUT_FORMATS.map((format) => (
            <option key={format} value={format}>
              {format}
            </option>
          ))}
        </select>
      </label>
      <button type="button" onClick={onConvert}>
        Convert
      </button>
      <p>Status: {status}</p>
      <h2>Directory batch</h2>
      <label>
        Directory{" "}
        <input value={directory} onChange={(event) => setDirectory(event.target.value)} />
      </label>
      <button type="button" onClick={() => void browseInto(setDirectory)}>
        Browse directory
      </button>
      <button type="button" onClick={onList}>
        List files
      </button>
      <ul>
        {visibleFiles.map((file) => (
          <li key={file}>
            <label>
              <input
                type="checkbox"
                checked={selectedFiles.includes(file)}
                onChange={() => toggleFile(file)}
              />
              {file}
            </label>
          </li>
        ))}
      </ul>
      <label>
        Output directory{" "}
        <input value={outputDir} onChange={(event) => setOutputDir(event.target.value)} />
      </label>
      <button type="button" onClick={() => void browseInto(setOutputDir)}>
        Browse output directory
      </button>
      <label>
        <input
          type="checkbox"
          checked={recursive}
          onChange={(event) => setRecursive(event.target.checked)}
        />{" "}
        Recursive
      </label>
      {INPUT_FORMATS.map((format) => (
        <button
          key={format}
          type="button"
          aria-pressed={inputFormats.includes(format)}
          onClick={() => toggleInputFormat(format)}
        >
          {format}
        </button>
      ))}
      <button type="button" onClick={() => setInputFormats([...INPUT_FORMATS])}>
        Add all input formats
      </button>
      <button type="button" onClick={() => setInputFormats([])}>
        Remove all input formats
      </button>
      <button type="button" onClick={() => onConvertDirectory()}>
        Convert directory
      </button>
      <label>
        Resample width{" "}
        <input
          type="number"
          min={1}
          value={resampleWidth}
          onChange={(event) => setResampleWidth(Number(event.target.value))}
        />
      </label>
      <label>
        Resample height{" "}
        <input
          type="number"
          min={1}
          value={resampleHeight}
          onChange={(event) => setResampleHeight(Number(event.target.value))}
        />
      </label>
      <label>
        Algorithm{" "}
        <select value={algorithm} onChange={(event) => setAlgorithm(event.target.value as (typeof ALGORITHMS)[number])}>
          {ALGORITHMS.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <input
          type="checkbox"
          checked={keepOriginalFormat}
          onChange={(event) => setKeepOriginalFormat(event.target.checked)}
        />{" "}
        Keep original format
      </label>
      <label>
        Video codec{" "}
        <select value={videoCodec} onChange={(event) => setVideoCodec(event.target.value as (typeof VIDEO_CODECS)[number])}>
          {VIDEO_CODECS.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <label>
        Audio codec{" "}
        <select value={audioCodec} onChange={(event) => setAudioCodec(event.target.value as (typeof AUDIO_CODECS)[number])}>
          {AUDIO_CODECS.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <label>
        CRF{" "}
        <input type="number" min={0} max={63} value={crf} onChange={(event) => setCrf(Number(event.target.value))} />
      </label>
      <button type="button" onClick={() => onBatch("convert")}>
        Convert Selected
      </button>
      <button type="button" onClick={() => onBatch("resample")}>
        Resample Selected
      </button>
      <button type="button" onClick={() => onBatch("reencode")}>
        Re-encode Selected
      </button>
      <button type="button" onClick={onCancelBatch}>
        Cancel
      </button>
      <p data-testid="convert-progress">
        Progress: {progress.done}/{progress.total}
      </p>
    </div>
  );
}

function completedBatchStatus(result: Record<string, unknown> | undefined): string {
  if (result === undefined) {
    return "batch ok";
  }
  const failed = result.failed;
  const errors = Array.isArray(result.errors)
    ? result.errors.filter((item): item is string => typeof item === "string" && item.length > 0)
    : [];
  const failedCount = typeof failed === "number" ? failed : 0;
  if ((typeof failed !== "number" || failed <= 0) && errors.length === 0) {
    return "batch ok";
  }
  const succeeded = typeof result.succeeded === "number" ? result.succeeded : 0;
  const count = failedCount > 0 ? failedCount : errors.length;
  const detail = errors.join(", ");
  return detail
    ? `batch failed: ${succeeded} succeeded, ${count} failed: ${detail}`
    : `batch failed: ${succeeded} succeeded, ${count} failed`;
}

async function pollJob(
  hostClient: HostClient,
  jobId: string,
  setProgress: (progress: { done: number; total: number }) => void,
): Promise<JobStatus> {
  let status = await hostClient.jobStatus(jobId);
  for (;;) {
    if (status.progress) {
      setProgress({ done: status.progress.done, total: status.progress.total });
    }
    if (status.state !== "queued" && status.state !== "running") {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
    status = await hostClient.jobStatus(jobId);
  }
}
