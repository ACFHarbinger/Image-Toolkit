import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { deskButtonClass, deskControlClass, DeskField } from "../components/common/DeskForm";
import { ThumbnailGallery } from "../components/common/ThumbnailGallery";

interface MediaResult {
  success: boolean;
  message?: string;
  algorithms?: ResampleAlgorithm[];
}

interface ResampleAlgorithm {
  id: string;
  content: string;
  kind: string;
  available: boolean;
  reason: string;
  containers?: string[];
}

const FALLBACK_ALGORITHMS: ResampleAlgorithm[] = [
  { id: "lanczos", content: "any", kind: "classical", available: true, reason: "" },
  { id: "bicubic", content: "any", kind: "classical", available: true, reason: "" },
  { id: "bilinear", content: "any", kind: "classical", available: true, reason: "" },
  { id: "nearest", content: "any", kind: "classical", available: true, reason: "" },
];

const ALGORITHM_GROUP_ORDER = ["realistic", "anime", "pixel", "any", "classical"];

function fileExtension(path: string): string {
  const base = fileName(path);
  const dot = base.lastIndexOf(".");
  return dot <= 0 ? "" : base.slice(dot + 1).toLowerCase();
}

function selectionContainers(paths: string[]): string[] {
  const kinds = new Set<string>();
  for (const path of paths) {
    kinds.add(fileExtension(path) === "gif" ? "gif" : "still");
  }
  return [...kinds];
}

function algorithmFits(row: ResampleAlgorithm, kinds: string[]): boolean {
  const containers = row.containers ?? ["gif", "still"];
  return kinds.every((kind) => containers.includes(kind));
}

function algorithmGroups(rows: ResampleAlgorithm[]): string[] {
  const present = new Set(rows.map((row) => row.content));
  const ordered = ALGORITHM_GROUP_ORDER.filter((group) => present.has(group));
  for (const group of present) {
    if (!ordered.includes(group)) {
      ordered.push(group);
    }
  }
  return ordered;
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
  const [algorithms, setAlgorithms] = useState<ResampleAlgorithm[]>(FALLBACK_ALGORITHMS);
  const [status, setStatus] = useState("ready");

  useEffect(() => {
    let cancelled = false;
    void runMedia("list_resample_algorithms", {}).then((result) => {
      if (cancelled || !result.algorithms || result.algorithms.length === 0) {
        return;
      }
      setAlgorithms(result.algorithms);
    }).catch(() => {
      // The four Pillow kernels stay selectable when the registry cannot be listed.
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = async () => {
    if (selected.length === 0) {
      setStatus("error: input required");
      return;
    }
    const kinds = selectionContainers(selected);
    const chosen = algorithms.find((row) => row.id === algorithm);
    if (chosen && !algorithmFits(chosen, kinds)) {
      setStatus(`failed: ${algorithm} does not apply to every selected file`);
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
        <p className="mt-1 text-sm text-it-muted-text">Resize an image or GIF. GIF backends are chosen from the registry, including classical scalers and neural models when their weights are available.</p>
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
          {algorithmGroups(algorithms.filter((row) => algorithmFits(row, selectionContainers(selected)))).map((group) => {
            const rows = algorithms.filter((row) => row.content === group && algorithmFits(row, selectionContainers(selected)));
            if (rows.length === 0) {
              return null;
            }
            return (
              <optgroup key={group} label={group}>
                {rows.map((row) => (
                  <option key={row.id} value={row.id} disabled={!row.available} title={row.reason}>
                    {row.available ? row.id : `${row.id} (${row.reason})`}
                  </option>
                ))}
              </optgroup>
            );
          })}
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
