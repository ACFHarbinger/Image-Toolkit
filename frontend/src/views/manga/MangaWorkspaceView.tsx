import React, { useState } from "react";
import {
  Palette,
  Film,
  Move,
  Play,
  Upload,
  Layers,
  Sparkles,
} from "lucide-react";
import type { HostClient } from "../../hostclient";

export type MangaMode = "colorization" | "animation" | "puppeteering";

/** Parse a point-set string like "10,20 30,40" into [x, y] pairs. */
export const parseCsgPoints = (text: string): Array<[number, number]> =>
  text
    .split(/[;\n]/)
    .flatMap((part) => part.trim().split(/\s+/))
    .filter(Boolean)
    .map((token) => token.split(",").map((value) => Number(value.trim())))
    .filter((pair) => pair.length === 2 && pair.every((value) => Number.isFinite(value)))
    .map((pair) => [pair[0], pair[1]] as [number, number]);

export interface MangaWorkspaceViewProps {
  initialMode?: MangaMode;
  showModal?: (
    message: string,
    type?: "info" | "success" | "error",
    duration?: number
  ) => void;
  hostClient?: HostClient;
}

export const MANGA_MODES = [
  {
    id: "colorization" as const,
    label: "Colorization",
    catalogId: "manga.colorization",
    icon: Palette,
    detail: "Levin scribble colorization & reference transfer",
  },
  {
    id: "animation" as const,
    label: "Animation",
    catalogId: "manga.animation",
    icon: Film,
    detail: "Screentone propagation & temporal coherence",
  },
  {
    id: "puppeteering" as const,
    label: "Puppeteering",
    catalogId: "manga.puppeteering",
    icon: Move,
    detail: "ARAP 2D mesh deformation & keyframing",
  },
];

export const MangaWorkspaceView: React.FC<MangaWorkspaceViewProps> = ({
  initialMode = "colorization",
  showModal,
  hostClient,
}) => {
  const [mode, setMode] = useState<MangaMode>(initialMode);
  const [sourcePath, setSourcePath] = useState<string>("");
  const [referencePath, setReferencePath] = useState<string>("");
  const [scribblePath, setScribblePath] = useState<string>("");
  const [framePathsText, setFramePathsText] = useState<string>("");
  const [controlPointsText, setControlPointsText] = useState<string>("");
  const [targetPointsText, setTargetPointsText] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("Workspace ready");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [meshVertices, setMeshVertices] = useState<number>(0);

  const handleExecute = async () => {
    if (!hostClient) {
      setStatusMessage("Error: Host client unavailable");
      if (showModal) showModal("Host client unavailable", "error");
      return;
    }
    if (mode !== "animation" && !sourcePath.trim()) {
      if (showModal) showModal("Please select a line-art or manga plate", "error");
      setStatusMessage("Error: Missing source manga image");
      return;
    }
    setIsProcessing(true);
    setStatusMessage(`Running ${mode} solver...`);
    try {
      if (mode === "colorization") {
        const reference = referencePath.trim();
        const scribble = scribblePath.trim();
        if (!reference && !scribble) {
          throw new Error("Provide a color reference or scribble hints");
        }
        const payload = reference
          ? await hostClient.csgColorizeReference({
              lineart_path: sourcePath.trim(),
              reference_path: reference,
            })
          : await hostClient.csgColorizeScribble({
              lineart_path: sourcePath.trim(),
              scribble_path: scribble,
            });
        if (!payload.success) throw new Error(payload.error ?? "colorization failed");
        setStatusMessage(`Colorization complete: ${payload.output_path ?? "no output path"}`);
        if (showModal) showModal("Colorization generated successfully", "success", 2000);
      } else if (mode === "animation") {
        const framePaths = framePathsText
          .split(/\r?\n/)
          .map((line) => line.trim())
          .filter(Boolean);
        if (framePaths.length === 0) throw new Error("Provide frame paths for the sequence");
        const payload = await hostClient.csgPropagateSequence({ frame_paths: framePaths });
        if (!payload.success) throw new Error(payload.error ?? "sequence propagation failed");
        setStatusMessage(`Propagated ${payload.frames_processed} frame(s)`);
        if (showModal) showModal("Sequence propagation complete", "success", 2000);
      } else {
        const controlPoints = parseCsgPoints(controlPointsText);
        const targetPoints = parseCsgPoints(targetPointsText);
        if (controlPoints.length === 0 || targetPoints.length === 0) {
          throw new Error("Provide control and target point sets (\"x,y x,y\")");
        }
        const payload = await hostClient.csgArapDeform({
          image_path: sourcePath.trim(),
          control_points: controlPoints,
          target_points: targetPoints,
        });
        if (!payload.success) throw new Error(payload.error ?? "ARAP deformation failed");
        setMeshVertices(payload.num_vertices);
        setStatusMessage(`ARAP deform complete: ${payload.output_path ?? "no output path"}`);
        if (showModal) showModal("Puppeteering pose generated successfully", "success", 2000);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setStatusMessage(`Error: ${message}`);
      if (showModal) showModal(message, "error");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-100 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-800 bg-gray-950/80">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-pink-950/80 border border-pink-800 rounded-lg text-pink-400">
            <Palette size={18} />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-wide flex items-center gap-2">
              Cel-Shaded Generator (CSG)
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-pink-950 border border-pink-800 text-pink-400 font-mono">
                WAVE 8 / E-03
              </span>
            </h2>
            <p className="text-xs text-gray-400">Manga Colorization, Screentone Animation, and ARAP Mesh Puppeteering</p>
          </div>
        </div>

        <button
          onClick={handleExecute}
          disabled={isProcessing}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-pink-600 hover:bg-pink-500 disabled:opacity-50 text-white rounded-lg shadow-sm transition-colors"
        >
          <Play size={14} /> {isProcessing ? "Solving..." : `Execute ${mode}`}
        </button>
      </div>

      {/* Mode Selector Tabs */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-gray-800/80 bg-gray-950/40 text-xs">
        {MANGA_MODES.map((m) => {
          const Icon = m.icon;
          const isActive = mode === m.id;
          return (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-colors ${
                isActive
                  ? "bg-pink-950/80 text-pink-300 font-semibold border border-pink-800/60"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
              }`}
            >
              <Icon size={14} />
              <span>{m.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main Workspace Body */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 min-h-0 overflow-y-auto">
        {/* Canvas / Preview Area */}
        <div className="lg:col-span-2 flex flex-col bg-gray-950/60 rounded-xl border border-gray-800 overflow-hidden">
          <div className="flex-1 relative flex items-center justify-center p-8 bg-[radial-gradient(#1f2937_1px,transparent_1px)] [background-size:16px_16px]">
            <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-800 rounded-xl p-12 text-center max-w-md">
              <Sparkles size={36} className="text-gray-600 mb-3" />
              <p className="text-sm font-medium text-gray-300">
                CSG Canvas Viewport — {MANGA_MODES.find((m) => m.id === mode)?.label}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Interactive scribble strokes, screentone frequency graphs, and ARAP mesh cage.
              </p>
            </div>
          </div>
          <div className="h-8 border-t border-gray-800 bg-gray-900/90 flex items-center justify-between px-4 text-xs font-mono text-gray-400">
            <span>Mode: manga.{mode}</span>
            <span>Mesh Vertices: {meshVertices}</span>
          </div>
        </div>

        {/* Controls Inspector */}
        <div className="flex flex-col gap-4 p-4 bg-gray-950/80 rounded-xl border border-gray-800">
          <h3 className="text-xs font-bold uppercase tracking-wider text-pink-400 flex items-center gap-1.5">
            <Layers size={14} /> Solver Parameters
          </h3>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Source Manga / Line-Art</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="/path/to/lineart.png"
                value={sourcePath}
                onChange={(e) => setSourcePath(e.target.value)}
                className="flex-1 text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 font-mono outline-none focus:border-pink-500"
              />
              <button
                onClick={() => setSourcePath("/home/user/manga/sample_page_01.png")}
                className="p-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700"
                title="Use sample path"
              >
                <Upload size={14} />
              </button>
            </div>
          </div>

          {mode === "colorization" && (
            <div className="space-y-2">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Color Reference (reference transfer)</label>
                <input
                  type="text"
                  placeholder="/path/to/reference_palette.png"
                  value={referencePath}
                  onChange={(e) => setReferencePath(e.target.value)}
                  className="w-full text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 font-mono outline-none focus:border-pink-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Scribble Hints (scribble colorization)</label>
                <input
                  type="text"
                  placeholder="/path/to/scribble_hints.png"
                  value={scribblePath}
                  onChange={(e) => setScribblePath(e.target.value)}
                  className="w-full text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 font-mono outline-none focus:border-pink-500"
                />
              </div>
            </div>
          )}

          {mode === "puppeteering" && (
            <div className="space-y-2">
              <div className="bg-gray-900/60 p-2.5 rounded-lg border border-gray-800/80 text-xs font-mono space-y-1 text-gray-400">
                <div className="flex justify-between">
                  <span>ARAP Rig:</span>
                  <span className="text-emerald-400">2D Triangular</span>
                </div>
                <div className="flex justify-between">
                  <span>Energy Model:</span>
                  <span>As-Rigid-As-Possible</span>
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Control Points ("x,y x,y")</label>
                <input
                  type="text"
                  placeholder="10,20 80,25"
                  value={controlPointsText}
                  onChange={(e) => setControlPointsText(e.target.value)}
                  className="w-full text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 font-mono outline-none focus:border-pink-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Target Points ("x,y x,y")</label>
                <input
                  type="text"
                  placeholder="12,24 95,20"
                  value={targetPointsText}
                  onChange={(e) => setTargetPointsText(e.target.value)}
                  className="w-full text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 font-mono outline-none focus:border-pink-500"
                />
              </div>
            </div>
          )}

          {mode === "animation" && (
            <div className="space-y-2">
              <div className="bg-gray-900/60 p-2.5 rounded-lg border border-gray-800/80 text-xs font-mono space-y-1 text-gray-400">
                <div className="flex justify-between">
                  <span>Screentone Guard:</span>
                  <span className="text-emerald-400">FFT BANDPASS</span>
                </div>
                <div className="flex justify-between">
                  <span>Temporal Solver:</span>
                  <span>Optimal Transport</span>
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Frame Sequence (one path per line)</label>
                <textarea
                  placeholder={"/path/to/frame_001.png\n/path/to/frame_002.png"}
                  value={framePathsText}
                  onChange={(e) => setFramePathsText(e.target.value)}
                  rows={4}
                  className="w-full text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 font-mono outline-none focus:border-pink-500"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-950 border-t border-gray-800 text-xs font-mono text-gray-400">
        <span className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-pink-500 animate-pulse" />
          {statusMessage}
        </span>
        <span>CSG Solver v3.2</span>
      </div>
    </div>
  );
};

export default MangaWorkspaceView;
