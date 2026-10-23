// Convert pilot view (#894).
// Injected HostClient instance (provided by the shell). No global declare.

import React, { useState } from "react";
import type { HostClient } from "../hostclient";

export interface ConvertPilotProps {
  hostClient: HostClient;
}

const OUTPUT_FORMATS = ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "tif", "ico", "gif"] as const;

type OutputFormat = (typeof OUTPUT_FORMATS)[number];

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

  return (
    <div data-testid="convert-pilot">
      <h1>Convert</h1>
      <p>Calls convert.convert via the injected HostClient.</p>
      <label>
        Input path{" "}
        <input value={inputPath} onChange={(e) => setInputPath(e.target.value)} />
      </label>
      <label>
        Output path{" "}
        <input value={outputPath} onChange={(e) => onOutputPath(e.target.value)} />
      </label>
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
    </div>
  );
}
