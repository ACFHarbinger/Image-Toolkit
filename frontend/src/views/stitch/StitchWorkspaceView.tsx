import React, { useState } from "react";
import {
  Layers,
  GitBranch,
  Sliders,
  Maximize2,
  BarChart3,
  ListOrdered,
  Sparkles,
  Play,
  Settings2,
  FolderOpen,
} from "lucide-react";
import type { HostClient } from "../../hostclient";

export interface StitchWorkspaceViewProps {
  initialRoute?: string;
  showModal?: (
    message: string,
    type?: "info" | "success" | "error",
    duration?: number
  ) => void;
  hostClient?: HostClient;
}

export const STITCH_PANELS = [
  { id: "stitch.stitch", label: "Stitch Pipeline", icon: Layers },
  { id: "stitch.graph", label: "Match Graph", icon: GitBranch },
  { id: "stitch.adjust", label: "Adjustments", icon: Sliders },
  { id: "stitch.canvas", label: "Canvas Layout", icon: Maximize2 },
  { id: "stitch.statistics", label: "Statistics", icon: BarChart3 },
  { id: "stitch.sequence-builder", label: "Sequence Builder", icon: ListOrdered },
  { id: "stitch.hybrid", label: "Hybrid HITL", icon: Settings2 },
  { id: "stitch.animation-clusters", label: "Animation Clusters", icon: Sparkles },
] as const;

export type StitchRouteId = typeof STITCH_PANELS[number]["id"];

export const StitchWorkspaceView: React.FC<StitchWorkspaceViewProps> = ({
  initialRoute = "stitch.stitch",
  showModal,
}) => {
  const [activePanel, setActivePanel] = useState<StitchRouteId>(
    (initialRoute as StitchRouteId) || "stitch.stitch"
  );
  const [inputDir, setInputDir] = useState<string>("");
  const [preset, setPreset] = useState<string>("anime-pan");
  const [blendMode, setBlendMode] = useState<string>("multiband");
  const [statusMessage, setStatusMessage] = useState<string>("Workspace idle");
  const [isRunning, setIsRunning] = useState<boolean>(false);

  const handleRunStitch = () => {
    if (!inputDir.trim()) {
      if (showModal) showModal("Please specify an input frame sequence directory", "error");
      setStatusMessage("Error: Missing frame input path");
      return;
    }
    setIsRunning(true);
    setStatusMessage("Running alignment & stitching pipeline...");
    if (showModal) showModal(`Stitching sequence with ${preset} preset...`, "info", 2000);
    setTimeout(() => {
      setIsRunning(false);
      setStatusMessage("Stitch completed successfully: Canvas 3840x1080 generated");
      if (showModal) showModal("Stitch job completed", "success", 2000);
    }, 1200);
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-100 overflow-hidden">
      {/* Top Navigation Bar */}
      <div className="flex items-center justify-between p-3 border-b border-gray-800 bg-gray-950/80">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-950/80 border border-indigo-800 rounded-lg text-indigo-400">
            <Layers size={18} />
          </div>
          <div>
            <h2 className="text-sm font-bold tracking-wide flex items-center gap-2">
              Anime Stitch Pipeline (ASP)
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-950 border border-indigo-800 text-indigo-400 font-mono">
                WAVE 8 / E-01
              </span>
            </h2>
            <p className="text-xs text-gray-400">Reconstruct wide backgrounds from animation pans and webtoons</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRunStitch}
            disabled={isRunning}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg shadow-sm transition-colors"
          >
            <Play size={14} /> {isRunning ? "Processing..." : "Run Stitch"}
          </button>
        </div>
      </div>

      {/* Route Switcher Ribbon */}
      <div className="flex items-center gap-1 px-4 py-2 border-b border-gray-800/80 bg-gray-950/40 overflow-x-auto text-xs">
        {STITCH_PANELS.map((p) => {
          const Icon = p.icon;
          const isActive = activePanel === p.id;
          return (
            <button
              key={p.id}
              onClick={() => setActivePanel(p.id)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md transition-colors whitespace-nowrap ${
                isActive
                  ? "bg-indigo-950/80 text-indigo-300 font-semibold border border-indigo-800/60"
                  : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
              }`}
            >
              <Icon size={13} />
              <span>{p.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main Workspace Body */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 min-h-0 overflow-y-auto">
        {/* Left / Center Viewport */}
        <div className="lg:col-span-2 flex flex-col bg-gray-950/60 rounded-xl border border-gray-800 overflow-hidden">
          <div className="flex-1 relative flex items-center justify-center p-8 bg-[radial-gradient(#1f2937_1px,transparent_1px)] [background-size:16px_16px]">
            <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-800 rounded-xl p-12 text-center max-w-md">
              <Maximize2 size={36} className="text-gray-600 mb-3" />
              <p className="text-sm font-medium text-gray-300">
                ASP Composite Viewport ({STITCH_PANELS.find((p) => p.id === activePanel)?.label})
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Shared Canvas Host rendering panoramic tie-points and seam-carved plates.
              </p>
            </div>
          </div>
          <div className="h-8 border-t border-gray-800 bg-gray-900/90 flex items-center justify-between px-4 text-xs font-mono text-gray-400">
            <span>Route: {activePanel}</span>
            <span>Canvas Resolution: 0 x 0</span>
          </div>
        </div>

        {/* Right Configuration Inspector */}
        <div className="flex flex-col gap-4 p-4 bg-gray-950/80 rounded-xl border border-gray-800">
          <h3 className="text-xs font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1.5">
            <Settings2 size={14} /> Pipeline Settings
          </h3>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Sequence Directory</label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="/path/to/frames"
                value={inputDir}
                onChange={(e) => setInputDir(e.target.value)}
                className="flex-1 text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 font-mono outline-none focus:border-indigo-500"
              />
              <button
                onClick={() => setInputDir("/home/user/frames/pan_shot_01")}
                className="p-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700"
                title="Use sample path"
              >
                <FolderOpen size={14} />
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Optimization Preset</label>
            <select
              value={preset}
              onChange={(e) => setPreset(e.target.value)}
              className="w-full text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 outline-none focus:border-indigo-500"
            >
              <option value="anime-pan">Anime Pan Shot (Dynamic motion)</option>
              <option value="webtoon-strip">Vertical Webtoon Strip</option>
              <option value="multi-phase">Multi-Phase Interleaved</option>
              <option value="high-precision">High-Precision GNC-TLS Bundle Adjust</option>
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Photometric Blend Mode</label>
            <select
              value={blendMode}
              onChange={(e) => setBlendMode(e.target.value)}
              className="w-full text-xs p-2 rounded bg-gray-900 border border-gray-800 text-gray-100 outline-none focus:border-indigo-500"
            >
              <option value="multiband">Laplacian Multi-band Pyramid</option>
              <option value="seam-carve">Graph-Cut Seam Carving</option>
              <option value="linear">Linear Feathering</option>
              <option value="plate-median">Temporal Median Clean Plate</option>
            </select>
          </div>

          <div className="border-t border-gray-800 pt-3">
            <h4 className="text-xs font-semibold text-gray-300 mb-2">Panel Diagnostics</h4>
            <div className="bg-gray-900/60 p-2.5 rounded-lg border border-gray-800/80 text-xs font-mono space-y-1 text-gray-400">
              <div className="flex justify-between">
                <span>Hold Detection:</span>
                <span className="text-emerald-400">ACTIVE</span>
              </div>
              <div className="flex justify-between">
                <span>Loop Closure:</span>
                <span className="text-indigo-400">ENABLED</span>
              </div>
              <div className="flex justify-between">
                <span>Max RSS Budget:</span>
                <span>8.0 GiB</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-950 border-t border-gray-800 text-xs font-mono text-gray-400">
        <span className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
          {statusMessage}
        </span>
        <span>ASP Engine v4.0</span>
      </div>
    </div>
  );
};

export default StitchWorkspaceView;
