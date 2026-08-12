import React, { useState } from "react";
import {
  Layers,
  Wand2,
  Sparkles,
  Sliders,
  Maximize2,
  Upload,
  Download,
  CheckCircle,
  Play,
  RotateCcw,
} from "lucide-react";
import { invoke } from "@tauri-apps/api/core";

interface HieEditorTabProps {
  showModal: (
    message: string,
    type: "info" | "success" | "error",
    duration?: number
  ) => void;
}

type AssistanceTool = "localized_tone" | "adjust_exposure" | "crop";

interface ToolOption {
  id: AssistanceTool;
  label: string;
  detail: string;
  icon: React.ReactNode;
}

export const HieEditorTab: React.FC<HieEditorTabProps> = ({ showModal }) => {
  const [selectedTool, setSelectedTool] = useState<AssistanceTool>("localized_tone");
  const [proposalReady, setProposalReady] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Ready for media sequence");
  const [saveState, setSaveState] = useState("READY");
  const [activeFrame, setActiveFrame] = useState(1);
  const [totalFrames, setTotalFrames] = useState(1);
  const [mediaPath, setMediaPath] = useState<string | null>(null);

  const tools: ToolOption[] = [
    {
      id: "localized_tone",
      label: "Brush Assistant",
      detail: "Localized retouching & dodge/burn",
      icon: <Wand2 size={16} className="text-cyan-400" />,
    },
    {
      id: "adjust_exposure",
      label: "Tone Agent",
      detail: "Global exposure & contrast harmonization",
      icon: <Sliders size={16} className="text-violet-400" />,
    },
    {
      id: "crop",
      label: "Composition Optimizer",
      detail: "Non-convex rule-of-thirds & balance crop",
      icon: <Maximize2 size={16} className="text-emerald-400" />,
    },
  ];

  const handleOpenMedia = async () => {
    try {
      showModal("Select image or video sequence for Hybrid Image Editor...", "info", 2000);
      setStatusMessage("Media sequence loaded: 1 frame (still image paradigm)");
      setSaveState("MODIFIED");
    } catch (err: any) {
      showModal(`Failed to open media: ${err?.message || err}`, "error");
    }
  };

  const handleExport = async () => {
    try {
      showModal("Exporting document via HIE render pipeline...", "info", 2500);
      setStatusMessage("Export complete");
    } catch (err: any) {
      showModal(`Export failed: ${err?.message || err}`, "error");
    }
  };

  const handlePreviewAssistance = () => {
    const active = tools.find((t) => t.id === selectedTool);
    setProposalReady(true);
    setStatusMessage(`${active?.label} proposal generated — accept to record`);
  };

  const handleAcceptProposal = () => {
    const active = tools.find((t) => t.id === selectedTool);
    setProposalReady(false);
    setSaveState("HISTORY UPDATED");
    setStatusMessage(`${active?.label} accepted into document history graph`);
    showModal(`${active?.label} proposal applied to document layer stack`, "success", 2000);
    setTimeout(() => setSaveState("READY"), 2000);
  };

  return (
    <div className="flex flex-col gap-4 p-2 sm:p-4 text-gray-100 bg-gray-900 rounded-2xl border border-gray-800">
      {/* Editor Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-3 bg-gray-950/80 rounded-xl border border-gray-800">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-500/10 rounded-lg border border-cyan-500/20 text-cyan-400">
            <Layers size={22} />
          </div>
          <div>
            <h2 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
              Hybrid Image Editor <span className="text-xs px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">HIE Core</span>
            </h2>
            <p className="text-xs text-gray-400">
              Multi-Modal Layer/Node Canvas &amp; ML/RL Co-Pilot Assistance
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-gray-900 border border-gray-800 text-gray-300">
            {saveState}
          </span>
          <button
            onClick={handleOpenMedia}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-gray-800 hover:bg-gray-700 text-white rounded-lg border border-gray-700 transition-colors"
          >
            <Upload size={14} /> Open Media
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors shadow-lg shadow-cyan-950"
          >
            <Download size={14} /> Export Document
          </button>
        </div>
      </div>

      {/* Main Workspace Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Canvas Column */}
        <div className="lg:col-span-3 flex flex-col gap-3">
          <div className="relative flex-1 min-h-[420px] bg-gray-950 rounded-xl border border-gray-800 flex flex-col items-center justify-center p-6 text-center overflow-hidden">
            {/* Checkerboard Pattern for transparent canvas state */}
            <div className="absolute inset-0 opacity-10 bg-[radial-gradient(#00f0ff_1px,transparent_1px)] [background-size:16px_16px]" />

            <div className="relative z-10 max-w-md flex flex-col items-center gap-3">
              <div className="p-4 bg-gray-900/90 rounded-2xl border border-gray-800 shadow-xl">
                <Sparkles size={36} className="text-cyan-400 animate-pulse" />
              </div>
              <h3 className="text-base font-semibold text-gray-200">
                Interactive Canvas Viewport
              </h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                Drop an image or video sequence here. Single images are processed as a 1-frame degenerate sequence paradigm for zero-refactor multi-modal compatibility.
              </p>
              <div className="flex items-center gap-2 text-xs text-cyan-400/80 bg-cyan-950/40 px-3 py-1.5 rounded-full border border-cyan-900/40">
                <span>Topological DAG Render Graph Active</span>
              </div>
            </div>
          </div>

          {/* Frame Sequence Timeline */}
          <div className="flex items-center justify-between gap-3 px-4 py-2 bg-gray-950/60 rounded-lg border border-gray-800 text-xs font-mono">
            <div className="flex items-center gap-2 text-gray-400">
              <Play size={12} className="text-cyan-400" />
              <span>Frame {String(activeFrame).padStart(2, "0")} / {String(totalFrames).padStart(2, "0")}</span>
            </div>
            <div className="flex-1 max-w-xs h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-cyan-500 w-full" />
            </div>
            <span className="text-gray-500">00:00:00.000</span>
          </div>
        </div>

        {/* Inspector Sidebar */}
        <div className="flex flex-col gap-4 p-4 bg-gray-950/80 rounded-xl border border-gray-800">
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                <Sparkles size={14} /> AI / RL Assistance
              </h4>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-mono">
                LOCAL HIE
              </span>
            </div>
            <p className="text-xs text-gray-400 mb-3">
              Select an intelligent co-pilot tool to generate inspectable proposal graphs.
            </p>

            <div className="flex flex-col gap-2">
              {tools.map((tool) => (
                <button
                  key={tool.id}
                  onClick={() => {
                    setSelectedTool(tool.id);
                    setProposalReady(false);
                  }}
                  className={`flex items-start gap-2.5 p-2.5 text-left rounded-lg border transition-all ${
                    selectedTool === tool.id
                      ? "bg-cyan-950/40 border-cyan-500/50 shadow-md"
                      : "bg-gray-900/50 border-gray-800 hover:bg-gray-900"
                  }`}
                >
                  <div className="mt-0.5">{tool.icon}</div>
                  <div>
                    <div className="text-xs font-semibold text-white">
                      {tool.label}
                    </div>
                    <div className="text-[11px] text-gray-400">
                      {tool.detail}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            <button
              onClick={handlePreviewAssistance}
              className="w-full mt-3 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-cyan-300 rounded-lg border border-gray-700 transition-colors"
            >
              <Sparkles size={14} /> Preview Assistance
            </button>

            {proposalReady && (
              <div className="mt-3 p-3 bg-cyan-950/60 border border-cyan-500/40 rounded-lg flex flex-col gap-2 text-xs">
                <div className="font-semibold text-cyan-300 flex items-center gap-1">
                  <CheckCircle size={14} /> Proposal Ready
                </div>
                <div className="text-gray-300">
                  Inspectable action proposal calculated by HIE middleware.
                </div>
                <button
                  onClick={handleAcceptProposal}
                  className="w-full mt-1 px-2.5 py-1.5 text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white rounded transition-colors"
                >
                  Accept into History
                </button>
              </div>
            )}
          </div>

          {/* Layer Stack */}
          <div className="border-t border-gray-800 pt-3 flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-gray-300">
              <span className="flex items-center gap-1.5">
                <Layers size={14} className="text-gray-400" /> Layer Stack
              </span>
              <span className="text-[10px] text-gray-500">Topological</span>
            </div>

            <div className="flex flex-col gap-1.5 text-xs font-medium">
              <div className="flex items-center justify-between p-2 rounded bg-cyan-950/30 border border-cyan-800/60 text-cyan-200">
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-cyan-400" />
                  Adjustment Group
                </span>
                <span className="text-[10px] font-mono text-cyan-400">Node DAG</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-gray-900 border border-gray-800 text-gray-300">
                <span className="flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-gray-500" />
                  Source Sequence
                </span>
                <span className="text-[10px] font-mono text-gray-500">100%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Status Bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-950/90 rounded-lg border border-gray-800 text-xs font-mono text-gray-400">
        <span className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          {statusMessage}
        </span>
        <span>HIE Engine v2.0</span>
      </div>
    </div>
  );
};

export default HieEditorTab;
