import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { deskButtonClass, deskControlClass, DeskField } from "../components/common/DeskForm";
import { ThumbnailGallery } from "../components/common/ThumbnailGallery";

interface MediaResult {
  success: boolean;
  message?: string;
}

async function runMedia(action: string, params: Record<string, unknown>): Promise<MediaResult> {
  return invoke<MediaResult>("media_subtab", { action, params });
}

export function CodecPanel() {
  const [inputPath, setInputPath] = useState("");
  const [outputPath, setOutputPath] = useState("");
  const [videoCodec, setVideoCodec] = useState("h264");
  const [audioCodec, setAudioCodec] = useState("aac");
  const [crf, setCrf] = useState(28);
  const [speed, setSpeed] = useState(2);
  const [status, setStatus] = useState("ready");

  const onSubmit = async () => {
    setStatus("re-encoding");
    try {
      const result = await runMedia("codec", {
        input_path: inputPath,
        output_path: outputPath,
        video_codec: videoCodec,
        audio_codec: audioCodec,
        crf,
        speed,
      });
      setStatus(result.success ? "ok" : `failed: ${result.message ?? "unknown"}`);
    } catch (err) {
      setStatus(`error: ${String(err)}`);
    }
  };

  return (
    <form className="mx-auto flex w-full max-w-3xl flex-col gap-4 rounded-2xl border border-it-border bg-it-surface p-6 shadow-sm" onSubmit={(event) => { event.preventDefault(); void onSubmit(); }}>
      <header>
        <h2 className="text-lg font-semibold">Codec</h2>
        <p className="mt-1 text-sm text-it-muted-text">Re-encode a video stream. Copy leaves that stream unchanged.</p>
      </header>
      <ThumbnailGallery
        multiple={false}
        extensions={["mp4", "mkv", "webm", "mov", "avi", "wmv"]}
        selected={inputPath ? [inputPath] : []}
        onSelectedChange={(paths) => setInputPath(paths[0] ?? "")}
      />
      <DeskField label="Input">
        <input className={deskControlClass} value={inputPath} onChange={(event) => setInputPath(event.target.value)} />
      </DeskField>
      <DeskField label="Output">
        <input className={deskControlClass} value={outputPath} onChange={(event) => setOutputPath(event.target.value)} />
      </DeskField>
      <DeskField label="Video codec">
        <select className={deskControlClass} value={videoCodec} onChange={(event) => setVideoCodec(event.target.value)}>
          <option value="copy">Keep Original (No Re-encode)</option>
          <option value="h264">H.264</option>
          <option value="hevc">H.265 / HEVC</option>
          <option value="av1">AV1</option>
          <option value="vp9">VP9</option>
        </select>
      </DeskField>
      <DeskField label="Audio codec">
        <select className={deskControlClass} value={audioCodec} onChange={(event) => setAudioCodec(event.target.value)}>
          <option value="copy">Keep Original (No Re-encode)</option>
          <option value="aac">AAC</option>
          <option value="opus">Opus</option>
          <option value="mp3">MP3</option>
          <option value="flac">FLAC</option>
        </select>
      </DeskField>
      <DeskField label="Speed">
        <select className={deskControlClass} value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
          <option value={0}>Fastest</option>
          <option value={1}>Fast</option>
          <option value={2}>Balanced</option>
          <option value={3}>Slow</option>
          <option value={4}>Best Quality</option>
        </select>
      </DeskField>
      <DeskField label="CRF">
        <input className={deskControlClass} type="number" min={0} max={63} value={crf} onChange={(event) => setCrf(Number(event.target.value))} />
      </DeskField>
      <button type="submit" className={deskButtonClass}>Re-encode</button>
      <p className="text-sm text-it-muted-text">Status: {status}</p>
    </form>
  );
}

function splitInputPaths(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function fileName(path: string): string {
  const slash = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  return slash >= 0 ? path.slice(slash + 1) : path;
}

/** `{dir}{stem}_resampled{ext}`, keeping the source separator. No extension stays `stem_resampled`. */
function siblingResampled(path: string): string {
  const slash = Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
  const dir = slash >= 0 ? path.slice(0, slash + 1) : "";
  const base = slash >= 0 ? path.slice(slash + 1) : path;
  const dot = base.lastIndexOf(".");
  if (dot <= 0) {
    return `${dir}${base}_resampled`;
  }
  return `${dir}${base.slice(0, dot)}_resampled${base.slice(dot)}`;
}

function pathsEqual(left: string, right: string): boolean {
  const norm = (value: string) => value.replace(/\\/g, "/").replace(/\/+$/, "");
  return norm(left) === norm(right);
}

function resampleDestination(path: string, output: string, count: number): string {
  if (count === 1 && output !== "") {
    return output;
  }
  if (output === "") {
    return siblingResampled(path);
  }
  // `\` only when the directory has backslashes and no forward slashes. One trailing separator is dropped.
  const sep = output.includes("\\") && !output.includes("/") ? "\\" : "/";
  let dir = output;
  if (dir.endsWith("/") || dir.endsWith("\\")) {
    dir = dir.slice(0, -1);
  }
  const base = fileName(path);
  return dir === "" ? `${sep}${base}` : `${dir}${sep}${base}`;
}

export function SamplerPanel() {
  const [selected, setSelected] = useState<string[]>([]);
  const [outputPath, setOutputPath] = useState("");
  const [mode, setMode] = useState<"factor" | "dimensions">("factor");
  const [factor, setFactor] = useState(0.5);
  const [width, setWidth] = useState(1280);
  const [height, setHeight] = useState(720);
  const [algorithm, setAlgorithm] = useState("lanczos");
  const [status, setStatus] = useState("ready");

  const onSubmit = async () => {
    if (selected.length === 0) {
      setStatus("error: input required");
      return;
    }
    setStatus("resampling");
    try {
      const batch = selected.map((input_path) => ({
        input_path,
        output_path: resampleDestination(input_path, outputPath, selected.length),
      }));
      if (batch.some((item) => selected.some((source) => pathsEqual(item.output_path, source)))) {
        setStatus("failed: refusing to replace a selected source");
        return;
      }
      if (batch.some((item, index) => batch.slice(0, index).some((previous) => pathsEqual(previous.output_path, item.output_path)))) {
        setStatus("failed: multiple inputs have the same output path");
        return;
      }
      for (const { input_path: inputPath, output_path: destination } of batch) {
        const result = await runMedia("resample", {
          input_path: inputPath,
          output_path: destination,
          batch,
          mode,
          factor,
          width,
          height,
          algorithm,
        });
        if (!result.success) {
          setStatus(`failed: ${result.message ?? "unknown"}`);
          return;
        }
      }
      setStatus("ok");
    } catch (err) {
      setStatus(`error: ${String(err)}`);
    }
  };

  return (
    <form className="mx-auto flex w-full max-w-3xl flex-col gap-4 rounded-2xl border border-it-border bg-it-surface p-6 shadow-sm" onSubmit={(event) => { event.preventDefault(); void onSubmit(); }}>
      <header>
        <h2 className="text-lg font-semibold">Sampler</h2>
        <p className="mt-1 text-sm text-it-muted-text">Resize an image or GIF by a scale factor or by target dimensions.</p>
      </header>
      <ThumbnailGallery selected={selected} onSelectedChange={setSelected} />
      <DeskField label="Input">
        <textarea
          className={deskControlClass}
          rows={3}
          value={selected.join("\n")}
          onChange={(event) => setSelected(splitInputPaths(event.target.value))}
        />
      </DeskField>
      <DeskField label="Output">
        <input className={deskControlClass} value={outputPath} onChange={(event) => setOutputPath(event.target.value)} />
      </DeskField>
      <DeskField label="Algorithm">
        <select className={deskControlClass} value={algorithm} onChange={(event) => setAlgorithm(event.target.value)}>
          <option value="lanczos">Lanczos</option>
          <option value="bicubic">Bicubic</option>
          <option value="bilinear">Bilinear</option>
          <option value="nearest">Nearest Neighbor</option>
        </select>
      </DeskField>
      <DeskField label="Scale mode">
        <select className={deskControlClass} value={mode} onChange={(event) => setMode(event.target.value as "factor" | "dimensions")}>
          <option value="factor">Scale factor</option>
          <option value="dimensions">Target dimensions</option>
        </select>
      </DeskField>
      {mode === "factor" ? (
        <DeskField label="Factor">
          <input className={deskControlClass} type="number" min={0.01} step={0.1} value={factor} onChange={(event) => setFactor(Number(event.target.value))} />
        </DeskField>
      ) : (
        <>
          <DeskField label="Width">
            <input className={deskControlClass} type="number" min={1} value={width} onChange={(event) => setWidth(Number(event.target.value))} />
          </DeskField>
          <DeskField label="Height">
            <input className={deskControlClass} type="number" min={1} value={height} onChange={(event) => setHeight(Number(event.target.value))} />
          </DeskField>
        </>
      )}
      <button
        type="submit"
        className={deskButtonClass}
        onClick={(event) => {
          event.preventDefault();
          void onSubmit();
        }}
      >
        Resample
      </button>
      <p className="text-sm text-it-muted-text">Status: {status}</p>
    </form>
  );
}
