import React, { useMemo, useState } from "react";
import {
  Layers,
  Wand2,
  Sparkles,
  Maximize2,
  Upload,
  Download,
  CheckCircle,
  Play,
  Sliders,
} from "lucide-react";
import { getHieHost } from "./host";

export interface HieEditorViewProps {
  showModal?: (
    message: string,
    type?: "info" | "success" | "error",
    duration?: number
  ) => void;
}

type AssistanceTool = "localized_tone" | "adjust_exposure" | "crop";

interface ToolOption {
  id: AssistanceTool;
  label: string;
  detail: string;
  policyName: string;
  icon: React.ReactNode;
}

/**
 * Hybrid Image Editor view (HIE, Wave 8 #915 / W0-03 Phase D #867).
 * Consolidated directly into Image-Toolkit's React/Tauri frontend.
 */
export const HieEditorView: React.FC<HieEditorViewProps> = ({ showModal }) => {
  const host = useMemo(() => getHieHost(), []);
  const [selectedTool, setSelectedTool] = useState<AssistanceTool>("localized_tone");
  const [proposalReady, setProposalReady] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Ready for media sequence");
  const [saveState, setSaveState] = useState("READY");
  const [activeFrame, setActiveFrame] = useState(1);
  const [totalFrames, setTotalFrames] = useState(1);
  const [documentId, setDocumentId] = useState<string | null>(null);

  const tools: ToolOption[] = [
    {
      id: "localized_tone",
      label: "Brush Assistant",
      detail: "Localized retouching & dodge/burn",
      policyName: "brush-assistant",
      icon: <Wand2 size={16} className="text-cyan-400" />,
    },
    {
      id: "adjust_exposure",
      label: "Tone Agent",
      detail: "Global exposure & contrast harmonization",
      policyName: "global-tone",
      icon: <Sliders size={16} className="text-violet-400" />,
    },
    {
      id: "crop",
      label: "Composition Optimizer",
      detail: "Non-convex rule-of-thirds & balance crop",
      policyName: "crop-composition",
      icon: <Maximize2 size={16} className="text-emerald-400" />,
    },
  ];

  const handleOpenMedia = async () => {
    try {
      if (showModal) showModal("Select image or video sequence for Hybrid Image Editor...", "info", 2000);
      const result = await host.openMedia();
      const openedId =
        result && typeof result === "object" && "documentId" in result
          ? result.documentId
          : undefined;
      if (openedId) {
        setDocumentId(openedId);
      } else {
        setDocumentId((prev) => prev ?? `local-${Date.now().toString(16)}`);
      }
      setActiveFrame(1);
      setTotalFrames(1);
      setStatusMessage("Media sequence loaded: 1 frame (still image paradigm)");
      setSaveState("MODIFIED");
      host.notify("Media sequence loaded");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      if (showModal) showModal(`Failed to open media: ${message}`, "error");
    }
  };

  const handleExport = async () => {
    try {
      await host.exportDocument(documentId ?? undefined);
      if (showModal) showModal("Exporting document via HIE render pipeline...", "info", 2500);
      setStatusMessage("Export complete");
      host.notify("Export complete");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      if (showModal) showModal(`Failed to export document: ${message}`, "error");
    }
  };

  const handlePreviewAssistance = async () => {
    try {
      setStatusMessage(`Computing ${selectedTool} assistance preview...`);
      const tool = tools.find((t) => t.id === selectedTool);
      if (host.previewPolicy && tool) {
        await host.previewPolicy(tool.policyName);
      }
      setProposalReady(true);
      setStatusMessage("Assistance proposal ready for inspection");
      if (showModal) showModal("Inspection proposal generated successfully", "success", 2000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      if (showModal) showModal(`Assistance preview failed: ${message}`, "error");
    }
  };

  const handleAcceptProposal = async () => {
    try {
      if (host.acceptProposal) {
        await host.acceptProposal(`prop-${Date.now().toString(16)}`);
      }
      setProposalReady(false);
      setSaveState("MODIFIED");
      setStatusMessage("Proposal integrated into document history");
      if (showModal) showModal("Proposal accepted and merged into node stack", "success", 2000);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      if (showModal) showModal(`Failed to accept proposal: ${message}`, "error");
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 text-gray-100 p-4 gap-4 overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-800 pb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-950/80 border border-cyan-800 rounded-lg text-cyan-400">
            <Sparkles size={20} />
          </div>
          <div>
            <h3 className="font-bold text-sm tracking-wide text-white flex items-center gap-2">
              Hybrid Image Editor
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-cyan-950 border border-cyan-800 text-cyan-400 font-mono">
                NON-DESTRUCTIVE
              </span>
            </h3>
            <p className="text-xs text-gray-400 font-mono">
              Document: {documentId || "UNTITLED"} • State: {saveState}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleOpenMedia}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg border border-gray-700 transition-colors"
          >
            <Upload size={14} /> Open Media
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg shadow-sm transition-colors"
          >
            <Download size={14} /> Export
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 flex-1 min-h-0">
        <div className="lg:col-span-3 flex flex-col bg-gray-950/60 rounded-xl border border-gray-800 overflow-hidden">
          <div className="flex-1 relative flex items-center justify-center p-8 bg-[radial-gradient(#1f2937_1px,transparent_1px)] [background-size:16px_16px]">
            <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-800 rounded-xl p-12 text-center max-w-sm">
              <Upload size={36} className="text-gray-600 mb-3" />
              <p className="text-sm font-medium text-gray-300">
                Media Workspace Viewport
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Drop an image or frame sequence to begin non-destructive editing.
              </p>
            </div>
          </div>

          <div className="h-10 border-t border-gray-800 bg-gray-900/90 flex items-center px-4 gap-3 text-xs font-mono">
            <div className="flex items-center gap-1 text-gray-400">
              <Play size={12} className="text-cyan-400" />
              <span>
                Frame {String(activeFrame).padStart(2, "0")} / {String(totalFrames).padStart(2, "0")}
              </span>
            </div>
            <div className="flex-1 max-w-xs h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div className="h-full bg-cyan-500 w-full" />
            </div>
            <span className="text-gray-500">00:00:00.000</span>
          </div>
        </div>

        <div className="flex flex-col gap-4 p-4 bg-gray-950/80 rounded-xl border border-gray-800 overflow-y-auto">
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
                    <div className="text-xs font-semibold text-white">{tool.label}</div>
                    <div className="text-[11px] text-gray-400">{tool.detail}</div>
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

      <div className="items-center justify-between px-3 py-1.5 bg-gray-950/90 rounded-lg border border-gray-800 text-xs font-mono text-gray-400 flex">
        <span className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          {statusMessage}
        </span>
        <span>HIE Engine v2.0</span>
      </div>
    </div>
  );
};

export default HieEditorView;
