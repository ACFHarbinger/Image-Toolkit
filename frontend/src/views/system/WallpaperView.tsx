import React, { useState, useEffect, useCallback } from "react";
import {
  Monitor as MonitorIcon,
  Play,
  Square,
  Settings2,
  Clock,
  Info,
  RefreshCw,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Layers,
  ExternalLink,
} from "lucide-react";
import type { HostClient } from "../../hostclient";
import { ThumbnailGallery } from "../../components/common/ThumbnailGallery";
import type {
  MonitorInfo,
  SetWallpaperParams,
  WallpaperGraphEdge,
  WallpaperGraphNode,
} from "../../../../contracts/generated/ts";

export interface WallpaperViewProps {
  hostClient: HostClient;
  showModal?: (message: string, type?: "info" | "error" | "success") => void;
}

export function WallpaperView({ hostClient, showModal }: WallpaperViewProps) {
  const [monitors, setMonitors] = useState<MonitorInfo[]>([]);
  const [desktopEnv, setDesktopEnv] = useState<string>("Detecting...");
  const [monitorPaths, setMonitorPaths] = useState<Record<string, string>>({});
  const [style, setStyle] = useState<"fill" | "fit" | "stretch" | "center" | "tile" | "span">("fill");
  const [bgColor, setBgColor] = useState<string>("");
  const [interval, setIntervalSeconds] = useState<number>(300);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [status, setStatus] = useState<string>("");
  const [statusType, setStatusType] = useState<"info" | "error" | "success">("info");
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedMonitorQueue, setSelectedMonitorQueue] = useState<string>("0");
  const [monitorQueues, setMonitorQueues] = useState<Record<string, string[]>>({});
  const [newQueuePath, setNewQueuePath] = useState<string>("");
  const [graphPath, setGraphPath] = useState<string>("");
  const [graphNodes, setGraphNodes] = useState<WallpaperGraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<WallpaperGraphEdge[]>([]);
  const [endBehavior, setEndBehavior] = useState<"repeat" | "stay" | "solid">("repeat");
  const [endColor, setEndColor] = useState<string>("#000000");
  const [nodePath, setNodePath] = useState<string>("");
  const [nodeDuration, setNodeDuration] = useState<number>(10);
  const [edgeFrom, setEdgeFrom] = useState<string>("");
  const [edgeTo, setEdgeTo] = useState<string>("");

  const refreshMonitors = useCallback(async () => {
    try {
      setLoading(true);
      const res = await hostClient.wallpaperGetMonitors();
      setMonitors(res.monitors);
      setDesktopEnv(res.desktop_environment);
      if (res.monitors.length > 0) {
        setSelectedMonitorQueue((prev) => (prev ? prev : res.monitors[0].id));
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Failed to detect monitors: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  }, [hostClient]);

  const loadSlideshowConfig = useCallback(async () => {
    try {
      const res = await hostClient.wallpaperSlideshowConfig({ update: false });
      setIntervalSeconds(res.interval_seconds || 300);
      setIsRunning(res.running === true);
      if (res.style) {
        setStyle(res.style as any);
      }
      setMonitorQueues(res.monitor_queues || {});
      if (res.current_paths) {
        setMonitorPaths((prev) => ({ ...prev, ...res.current_paths }));
      }
    } catch (err) {
      console.warn("Could not load slideshow config:", err);
    }
  }, [hostClient]);

  useEffect(() => {
    refreshMonitors();
    loadSlideshowConfig();
  }, [refreshMonitors, loadSlideshowConfig]);

  const handleApplyWallpaper = async () => {
    const validPaths = Object.fromEntries(
      Object.entries(monitorPaths).filter(([_, p]) => p && p.trim().length > 0)
    );
    if (Object.keys(validPaths).length === 0) {
      setStatus("Error: Please specify at least one valid image path");
      setStatusType("error");
      return;
    }

    try {
      setLoading(true);
      setStatus("Applying wallpaper...");
      setStatusType("info");
      const params: SetWallpaperParams = {
        path_map: validPaths,
        style,
        background_color: bgColor.trim() ? bgColor.trim() : null,
      };
      const res = await hostClient.wallpaperSet(params);
      if (res.success) {
        setStatus(res.message || "Wallpaper applied successfully!");
        setStatusType("success");
        if (showModal) showModal(res.message, "success");
      } else {
        setStatus(res.message || "Failed to set wallpaper");
        setStatusType("error");
        if (showModal) showModal(res.message, "error");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Error: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSlideshow = async () => {
    const nextState = !isRunning;
    try {
      setLoading(true);
      // Persist config first
      await hostClient.wallpaperSlideshowConfig({
        update: true,
        interval_seconds: interval,
        style,
        monitor_queues: monitorQueues,
        current_paths: monitorPaths,
      });

      const res = await hostClient.wallpaperSlideshowToggle({ running: nextState });
      setIsRunning(res.running);
      setStatus(res.message || (nextState ? "Slideshow started" : "Slideshow stopped"));
      setStatusType("success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Failed to toggle slideshow: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    try {
      setLoading(true);
      await hostClient.wallpaperSlideshowConfig({
        update: true,
        interval_seconds: interval,
        style,
        monitor_queues: monitorQueues,
        current_paths: monitorPaths,
      });
      setStatus("Slideshow configuration saved successfully");
      setStatusType("success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Failed to save config: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  const handleAddQueueItem = () => {
    if (!newQueuePath.trim()) return;
    const currentList = monitorQueues[selectedMonitorQueue] || [];
    setMonitorQueues({
      ...monitorQueues,
      [selectedMonitorQueue]: [...currentList, newQueuePath.trim()],
    });
    setNewQueuePath("");
  };

  const handleRemoveQueueItem = (idx: number) => {
    const currentList = monitorQueues[selectedMonitorQueue] || [];
    setMonitorQueues({
      ...monitorQueues,
      [selectedMonitorQueue]: currentList.filter((_, i) => i !== idx),
    });
  };

  const handleAddGraphNode = () => {
    const path = nodePath.trim();
    if (!path) return;
    const id = `n${graphNodes.length + 1}`;
    setGraphNodes([...graphNodes, { id, path, duration_seconds: Math.max(1, Math.floor(nodeDuration) || 1) }]);
    setNodePath("");
  };

  const handleAddGraphEdge = () => {
    if (!edgeFrom || !edgeTo) return;
    setGraphEdges([...graphEdges, { source: edgeFrom, target: edgeTo }]);
  };

  const handleSaveGraph = async () => {
    const path = graphPath.trim();
    if (!path) {
      setStatus("Error: graph file path is required");
      setStatusType("error");
      return;
    }
    try {
      setLoading(true);
      const res = await hostClient.wallpaperMonitorGraph({
        update: true,
        path,
        nodes: graphNodes,
        edges: graphEdges,
        end_behavior: endBehavior,
        end_color: endColor,
      });
      if (res.error) {
        setStatus(res.error);
        setStatusType("error");
        return;
      }
      setStatus(`Graph saved ${res.path}`);
      setStatusType("success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Failed to save graph: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  const handleLoadGraph = async () => {
    const path = graphPath.trim();
    if (!path) {
      setStatus("Error: graph file path is required");
      setStatusType("error");
      return;
    }
    try {
      setLoading(true);
      const res = await hostClient.wallpaperMonitorGraph({ update: false, path });
      setGraphNodes(res.nodes);
      setGraphEdges(res.edges);
      setEndBehavior(res.end_behavior);
      setEndColor(res.end_color || "#000000");
      setStatus(res.error ? res.error : `Graph loaded ${res.path}`);
      setStatusType(res.error ? "error" : "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatus(`Failed to load graph: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  // The queue picker starts at "0", which is not a monitor id until the user picks one.
  const galleryMonitorId = monitors.some((monitor) => monitor.id === selectedMonitorQueue)
    ? selectedMonitorQueue
    : monitors[0]?.id;
  const galleryPath = galleryMonitorId ? monitorPaths[galleryMonitorId] || "" : "";

  const handleGallerySelect = (paths: string[]) => {
    if (!galleryMonitorId) return;
    setMonitorPaths((prev) => ({ ...prev, [galleryMonitorId]: paths[0] ?? "" }));
  };

  const handleMoveQueueItem = (idx: number, direction: "up" | "down") => {
    const currentList = [...(monitorQueues[selectedMonitorQueue] || [])];
    const targetIdx = direction === "up" ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= currentList.length) return;
    const [item] = currentList.splice(idx, 1);
    currentList.splice(targetIdx, 0, item);
    setMonitorQueues({
      ...monitorQueues,
      [selectedMonitorQueue]: currentList,
    });
  };

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden text-gray-800 dark:text-gray-100">
      {/* Header */}
      <div className="p-4 border-b dark:border-gray-800 bg-white dark:bg-gray-800/60 flex justify-between items-center shadow-sm">
        <div className="flex items-center gap-3">
          <MonitorIcon className="text-violet-500 w-6 h-6" />
          <div>
            <h2 className="text-lg font-bold flex items-center gap-2">
              Wallpaper & Multi-Monitor Presenter
            </h2>
            <span className="text-xs text-gray-500 dark:text-gray-400">
              Desktop Environment: <strong className="text-violet-600 dark:text-violet-400">{desktopEnv}</strong>
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isRunning && (
            <div className="flex items-center gap-1.5 px-3 py-1 bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300 rounded-full text-xs font-mono animate-pulse">
              <Clock size={13} /> Slideshow Active ({interval}s)
            </div>
          )}
          <button
            type="button"
            data-testid="open-slideshow-window-button"
            onClick={async () => {
              try {
                const { popOut } = await import("../../shell/windows");
                await popOut("slideshow");
              } catch (err) {
                console.warn("Could not pop out slideshow window:", err);
              }
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-violet-50 text-violet-700 hover:bg-violet-100 dark:bg-violet-950 dark:text-violet-300 dark:hover:bg-violet-900 border border-violet-200 dark:border-violet-800 transition"
            title="Open companion Slideshow Presenter Window"
          >
            <ExternalLink size={14} /> Open Presenter Window
          </button>
          <button
            onClick={refreshMonitors}
            disabled={loading}
            className="p-2 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
            title="Refresh monitor layout"
            aria-label="Refresh monitors"
          >
            <RefreshCw size={15} className={loading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Connected Monitors Discovery */}
        <section className="bg-white dark:bg-gray-800 p-5 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 flex items-center gap-2">
              <Layers size={16} /> Connected Monitors ({monitors.length})
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {monitors.map((m) => (
              <div
                key={m.id}
                className="p-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/50 flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-semibold text-sm">
                      {m.name} {m.is_primary ? "(Primary)" : ""}
                    </span>
                    <span className="text-xs font-mono text-gray-400">
                      {m.width}x{m.height} @ ({m.x}, {m.y})
                    </span>
                  </div>
                  <label className="block text-xs text-gray-500 mb-1">Assigned Image Path</label>
                  <input
                    type="text"
                    placeholder="/absolute/path/to/wallpaper.png"
                    value={monitorPaths[m.id] || ""}
                    onChange={(e) =>
                      setMonitorPaths({ ...monitorPaths, [m.id]: e.target.value })
                    }
                    className="w-full text-xs p-2 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 font-mono outline-none focus:ring-1 focus:ring-violet-500"
                  />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <ThumbnailGallery
              multiple={false}
              directoryLabel="Image directory"
              selected={galleryPath ? [galleryPath] : []}
              onSelectedChange={handleGallerySelect}
            />
          </div>
        </section>

        {/* Configuration Controls */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Static Settings */}
          <div className="bg-white dark:bg-gray-800 p-5 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
                <Settings2 size={16} className="text-gray-400" /> Static Scaling & Style
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase">
                    Wallpaper Scaling
                  </label>
                  <select
                    value={style}
                    onChange={(e) => setStyle(e.target.value as any)}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white p-2 text-sm focus:ring-2 focus:ring-violet-500 outline-none"
                  >
                    <option value="fill">Fill (Zoom to Canvas)</option>
                    <option value="fit">Fit (Letterbox / Keep Proportions)</option>
                    <option value="stretch">Stretch (Exact Fit)</option>
                    <option value="center">Center (Original Size)</option>
                    <option value="tile">Tile (Repeat)</option>
                    <option value="span">Span (Across All Connected Monitors)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1 uppercase">
                    Background Color / Matte (#RRGGBB)
                  </label>
                  <input
                    type="text"
                    placeholder="#000000"
                    value={bgColor}
                    onChange={(e) => setBgColor(e.target.value)}
                    className="w-full text-sm p-2 rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white font-mono outline-none"
                  />
                </div>
              </div>
            </div>
            <button
              onClick={handleApplyWallpaper}
              disabled={loading || Object.keys(monitorPaths).length === 0}
              className={`w-full mt-6 py-2.5 rounded-lg font-bold text-white transition shadow-md
                ${Object.keys(monitorPaths).length > 0
                  ? "bg-gradient-to-r from-emerald-500 to-teal-600 hover:shadow-emerald-500/20"
                  : "bg-gray-400 cursor-not-allowed"
                }`}
            >
              Apply Static Wallpaper
            </button>
          </div>

          {/* Slideshow Daemon & Queue */}
          <div className="bg-white dark:bg-gray-800 p-5 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
                <Play size={16} className="text-gray-400" /> Slideshow Daemon & Queue
              </h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs font-medium text-gray-500 mb-1 uppercase">
                    <span>Rotation Interval</span>
                    <span className="font-mono">{interval}s</span>
                  </div>
                  <input
                    type="range"
                    min="10"
                    max="1800"
                    step="10"
                    value={interval}
                    onChange={(e) => setIntervalSeconds(Number(e.target.value))}
                    className="w-full accent-violet-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1 uppercase">
                    Monitor Queue Selection
                  </label>
                  <select
                    value={selectedMonitorQueue}
                    onChange={(e) => setSelectedMonitorQueue(e.target.value)}
                    className="w-full rounded-lg border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white p-2 text-sm outline-none"
                  >
                    {monitors.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name} (Display {m.id})
                      </option>
                    ))}
                  </select>
                </div>
                {/* Queue list */}
                <div className="space-y-1.5 max-h-36 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded p-2 text-xs">
                  {(monitorQueues[selectedMonitorQueue] || []).map((path, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between bg-gray-100 dark:bg-gray-700/60 p-1.5 rounded"
                    >
                      <span className="truncate max-w-[200px] font-mono">{path}</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleMoveQueueItem(idx, "up")}
                          disabled={idx === 0}
                          className="p-1 hover:text-violet-500 disabled:opacity-30"
                          title="Move up"
                        >
                          <ArrowUp size={12} />
                        </button>
                        <button
                          onClick={() => handleMoveQueueItem(idx, "down")}
                          disabled={idx === (monitorQueues[selectedMonitorQueue]?.length || 0) - 1}
                          className="p-1 hover:text-violet-500 disabled:opacity-30"
                          title="Move down"
                        >
                          <ArrowDown size={12} />
                        </button>
                        <button
                          onClick={() => handleRemoveQueueItem(idx)}
                          className="p-1 text-red-500 hover:text-red-700"
                          title="Remove item"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                  ))}
                  {(!monitorQueues[selectedMonitorQueue] ||
                    monitorQueues[selectedMonitorQueue].length === 0) && (
                    <div className="text-gray-400 text-center py-2">Queue is empty</div>
                  )}
                </div>
                {/* Add path to queue */}
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="/path/to/image.png"
                    value={newQueuePath}
                    onChange={(e) => setNewQueuePath(e.target.value)}
                    className="flex-1 text-xs p-1.5 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white font-mono"
                  />
                  <button
                    onClick={handleAddQueueItem}
                    className="px-3 py-1 bg-violet-600 text-white rounded text-xs font-semibold hover:bg-violet-700 flex items-center gap-1"
                  >
                    <Plus size={12} /> Add
                  </button>
                </div>
              </div>
            </div>
            <div className="flex gap-2 mt-6">
              <button
                onClick={handleSaveConfig}
                disabled={loading}
                className="flex-1 py-2.5 rounded-lg font-semibold text-xs border border-gray-300 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 transition"
              >
                Save Configuration
              </button>
              <button
                onClick={handleToggleSlideshow}
                disabled={loading}
                className={`flex-1 py-2.5 rounded-lg font-bold text-white transition flex items-center justify-center gap-2 shadow-md
                  ${isRunning
                    ? "bg-red-500 hover:bg-red-600 shadow-red-500/20"
                    : "bg-violet-600 hover:bg-violet-700 shadow-violet-500/20"
                  }`}
              >
                {isRunning ? (
                  <>
                    <Square size={16} fill="currentColor" /> Stop Slideshow
                  </>
                ) : (
                  <>
                    <Play size={16} fill="currentColor" /> Start Slideshow
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        <section className="bg-white dark:bg-gray-800 p-5 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
          <h3 className="text-sm font-bold mb-4">Monitor display graph</h3>
          <div className="space-y-3 text-sm">
            <label className="block text-xs font-medium text-gray-500 uppercase">
              Graph file
              <input
                type="text"
                aria-label="Graph file"
                placeholder="/tmp/monitor-graph.json"
                value={graphPath}
                onChange={(e) => setGraphPath(e.target.value)}
                className="mt-1 w-full text-xs p-2 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 font-mono"
              />
            </label>
            <div className="flex flex-wrap gap-2 items-end">
              <label className="text-xs">
                Node path
                <input
                  type="text"
                  aria-label="Node path"
                  value={nodePath}
                  onChange={(e) => setNodePath(e.target.value)}
                  className="block mt-1 text-xs p-1.5 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700 font-mono"
                />
              </label>
              <label className="text-xs">
                Duration seconds
                <input
                  type="number"
                  aria-label="Duration seconds"
                  min={1}
                  value={nodeDuration}
                  onChange={(e) => setNodeDuration(Number(e.target.value))}
                  className="block mt-1 w-24 text-xs p-1.5 rounded border border-gray-300 dark:border-gray-600 dark:bg-gray-700"
                />
              </label>
              <button type="button" onClick={handleAddGraphNode} className="px-3 py-1.5 bg-violet-600 text-white rounded text-xs">
                Add node
              </button>
            </div>
            <ul className="text-xs font-mono space-y-1">
              {graphNodes.map((node) => (
                <li key={node.id}>
                  {node.id} {node.path} {node.duration_seconds}s
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap gap-2 items-end">
              <label className="text-xs">
                From
                <select aria-label="Edge from" value={edgeFrom} onChange={(e) => setEdgeFrom(e.target.value)} className="block mt-1 text-xs p-1.5 rounded border dark:bg-gray-700">
                  <option value="">source</option>
                  {graphNodes.map((node) => (
                    <option key={node.id} value={node.id}>{node.id}</option>
                  ))}
                </select>
              </label>
              <label className="text-xs">
                To
                <select aria-label="Edge to" value={edgeTo} onChange={(e) => setEdgeTo(e.target.value)} className="block mt-1 text-xs p-1.5 rounded border dark:bg-gray-700">
                  <option value="">target</option>
                  {graphNodes.map((node) => (
                    <option key={`t-${node.id}`} value={node.id}>{node.id}</option>
                  ))}
                </select>
              </label>
              <button type="button" onClick={handleAddGraphEdge} className="px-3 py-1.5 border rounded text-xs">
                Add edge
              </button>
            </div>
            <label className="block text-xs">
              End behavior
              <select
                aria-label="End behavior"
                value={endBehavior}
                onChange={(e) => setEndBehavior(e.target.value as "repeat" | "stay" | "solid")}
                className="block mt-1 text-xs p-1.5 rounded border dark:bg-gray-700"
              >
                <option value="repeat">repeat</option>
                <option value="stay">stay</option>
                <option value="solid">solid</option>
              </select>
            </label>
            {endBehavior === "solid" && (
              <label className="block text-xs">
                End color
                <input
                  type="text"
                  aria-label="End color"
                  value={endColor}
                  onChange={(e) => setEndColor(e.target.value)}
                  className="block mt-1 text-xs p-1.5 rounded border font-mono dark:bg-gray-700"
                />
              </label>
            )}
            <svg data-testid="monitor-graph" width="480" height="72" role="img" aria-label="Monitor display graph">
              {graphEdges.map((edge, index) => {
                const source = graphNodes.findIndex((node) => node.id === edge.source);
                const target = graphNodes.findIndex((node) => node.id === edge.target);
                if (source < 0 || target < 0) return null;
                return (
                  <line
                    key={`${edge.source}-${edge.target}-${index}`}
                    x1={24 + source * 110 + 88}
                    y1={36}
                    x2={24 + target * 110}
                    y2={36}
                    stroke="currentColor"
                  />
                );
              })}
              {graphNodes.map((node, index) => (
                <g key={node.id}>
                  <rect x={24 + index * 110} y={16} width={88} height={40} fill="none" stroke="currentColor" />
                  <text x={28 + index * 110} y={40} fontSize="11">{node.id}</text>
                </g>
              ))}
            </svg>
            <div className="flex gap-2">
              <button type="button" onClick={handleSaveGraph} disabled={loading} className="px-3 py-1.5 bg-violet-600 text-white rounded text-xs">
                Save graph
              </button>
              <button type="button" onClick={handleLoadGraph} disabled={loading} className="px-3 py-1.5 border rounded text-xs">
                Load graph
              </button>
            </div>
          </div>
        </section>

        {/* Live Status Notification */}
        {status && (
          <div
            role="status"
            aria-live="polite"
            className={`p-3 rounded-lg text-sm font-medium transition ${
              statusType === "error"
                ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800"
                : statusType === "success"
                ? "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                : "bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800"
            }`}
          >
            {status}
          </div>
        )}
      </div>
    </div>
  );
}

export default WallpaperView;
