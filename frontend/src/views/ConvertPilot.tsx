// Convert pilot view (#894).
// Injected HostClient instance (provided by the shell). No global declare.

import React, { useState } from "react";
import type { HostClient } from "../hostclient";

export interface ConvertPilotProps {
  hostClient: HostClient;
}

export function ConvertPilot({ hostClient }: ConvertPilotProps) {
  const [inputPath, setInputPath] = useState("");
  const [outputPath, setOutputPath] = useState("");
  const [status, setStatus] = useState("ready");

  const onConvert = async () => {
    setStatus("calling");
    try {
      const result = await hostClient.convert({
        input_path: inputPath,
        output_path: outputPath,
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
        <input value={outputPath} onChange={(e) => setOutputPath(e.target.value)} />
      </label>
      <button type="button" onClick={onConvert}>
        Convert
      </button>
      <p>Status: {status}</p>
    </div>
  );
}
