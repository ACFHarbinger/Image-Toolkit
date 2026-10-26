import React, { useState, useEffect, useCallback } from "react";
import {
  Monitor as MonitorIcon,
  Play,
  Square,
  ArrowUp,
  ArrowDown,
  Trash2,
  CheckCircle2,
  Clock,
  Settings2,
  Plus,
  RefreshCw,
  Image as ImageIcon,
} from "lucide-react";
import type { HostClient } from "../hostclient";
import type { MonitorInfo } from "../../../contracts/generated/ts";

export interface SlideshowPresenterWindowProps {
  hostClient: HostClient;
}

export function SlideshowPresenterWindow({
  hostClient,
}: SlideshowPresenterWindowProps): React.ReactElement {
  const [monitors, setMonitors] = useState<MonitorInfo[]>([]);
  const [selectedMonitor, setSelectedMonitor] = useState<string>("0");
  const [queues, setQueues] = useState<Record<string, string[]>>({});
  const [currentPaths, setCurrentPaths] = useState<Record<string, string>>({});
  const [intervalSeconds, setIntervalSeconds] = useState<number>(300);
  const [style, setStyle] = useState<"fill" | "fit" | "stretch" | "center" | "tile" | "span">("fill");
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [newPath, setNewPath] = useState<string>("");
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [statusType, setStatusType] = useState<"info" | "success" | "error">("info");
  const [loading, setLoading] = useState<boolean>(false);

  // Load monitors and config. Note: does NOT call wallpaperSet on mount.
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const monRes = await hostClient.wallpaperGetMonitors();
      setMonitors(monRes.monitors);
      if (monRes.monitors.length > 0 && !selectedMonitor) {
        setSelectedMonitor(monRes.monitors[0].id);
      }

      const cfgRes = await hostClient.wallpaperSlideshowConfig({ update: false });
      setIntervalSeconds(cfgRes.interval_seconds || 300);
      if (cfgRes.style) {
        setStyle(cfgRes.style as "fill" | "fit" | "stretch" | "center" | "tile" | "span");
      }
      setQueues(cfgRes.monitor_queues || {});
      setCurrentPaths(cfgRes.current_paths || {});
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusMessage(`Failed to load data: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  }, [hostClient, selectedMonitor]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const activeQueue = queues[selectedMonitor] || [];
  const currentActivePath = currentPaths[selectedMonitor] || "";

  const handleSaveConfig = async (
    nextQueues = queues,
    nextInterval = intervalSeconds,
    nextStyle = style,
  ) => {
    try {
      setLoading(true);
      const res = await hostClient.wallpaperSlideshowConfig({
        update: true,
        interval_seconds: nextInterval,
        style: nextStyle,
        monitor_queues: nextQueues,
        current_paths: currentPaths,
      });
      setQueues(res.monitor_queues || nextQueues);
      setStatusMessage("Slideshow configuration saved");
      setStatusType("success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusMessage(`Save error: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleDaemon = async () => {
    const nextRunning = !isRunning;
    try {
      setLoading(true);
      // Persist config before toggling
      await hostClient.wallpaperSlideshowConfig({
        update: true,
        interval_seconds: intervalSeconds,
        style,
        monitor_queues: queues,
        current_paths: currentPaths,
      });

      const res = await hostClient.wallpaperSlideshowToggle({ running: nextRunning });
      setIsRunning(res.running);
      setStatusMessage(res.message);
      setStatusType("success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusMessage(`Toggle error: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  const handleMoveItem = async (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= activeQueue.length) return;

    const updated = [...activeQueue];
    const [moved] = updated.splice(index, 1);
    updated.splice(targetIndex, 0, moved);

    const nextQueues = { ...queues, [selectedMonitor]: updated };
    setQueues(nextQueues);
    await handleSaveConfig(nextQueues);
  };

  const handleRemoveItem = async (index: number) => {
    const updated = activeQueue.filter((_, i) => i !== index);
    const nextQueues = { ...queues, [selectedMonitor]: updated };
    setQueues(nextQueues);
    await handleSaveConfig(nextQueues);
  };

  const handleAddItem = async () => {
    const trimmed = newPath.trim();
    if (!trimmed) return;
    const updated = [...activeQueue, trimmed];
    const nextQueues = { ...queues, [selectedMonitor]: updated };
    setQueues(nextQueues);
    setNewPath("");
    await handleSaveConfig(nextQueues);
  };

  const handleSetActiveWallpaper = async (path: string) => {
    try {
      setLoading(true);
      const res = await hostClient.wallpaperSet({
        path_map: { [selectedMonitor]: path },
        style,
      });
      if (res.success) {
        const nextCurrent = { ...currentPaths, [selectedMonitor]: path };
        setCurrentPaths(nextCurrent);
        setStatusMessage(res.message);
        setStatusType("success");
      } else {
        setStatusMessage(res.message || "Failed to set wallpaper");
        setStatusType("error");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setStatusMessage(`Error setting active wallpaper: ${msg}`);
      setStatusType("error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      data-testid="slideshow-presenter-window"
      className="flex min-h-screen flex-col bg-gray-50 text-gray-900 dark:bg-gray-950 dark:text-gray-100"
    >
      {/* Header */}
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
        <div className="flex items-center gap-3">
          <MonitorIcon className="text-violet-600 dark:text-violet-400" size={24} />
          <div>
            <h1 className="text-lg font-bold">Slideshow Presenter</h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Per-Monitor Wallpaper Queue & Rotation Controller
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div
            data-testid="slideshow-daemon-badge"
            className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
              isRunning
                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 animate-pulse"
                : "bg-gray-200 text-gray-700 dark:bg-gray-800 dark:text-gray-400"
            }`}
          >
            <Clock size={14} />
            <span>{isRunning ? `Running (${intervalSeconds}s)` : "Daemon Stopped"}</span>
          </div>
          <button
            type="button"
            data-testid="refresh-button"
            onClick={() => void loadData()}
            className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
            title="Refresh monitor and queue data"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </header>

      {/* Main Workspace */}
      <div className="flex flex-1 flex-col md:flex-row gap-6 p-6">
        {/* Left Column: Monitors & Controls */}
        <div className="w-full md:w-80 flex flex-col gap-6">
          {/* Monitor Selection */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <h2 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3">
              Select Physical Monitor
            </h2>
            <div className="flex flex-col gap-2">
              {monitors.map((m) => {
                const isSelected = selectedMonitor === m.id;
                const mQueue = queues[m.id] || [];
                return (
                  <button
                    key={m.id}
                    type="button"
                    data-testid={`monitor-tab-${m.id}`}
                    onClick={() => setSelectedMonitor(m.id)}
                    className={`flex items-center justify-between rounded-lg p-3 text-left transition-all ${
                      isSelected
                        ? "bg-violet-600 text-white shadow"
                        : "bg-gray-50 text-gray-700 hover:bg-gray-100 dark:bg-gray-800/60 dark:text-gray-300 dark:hover:bg-gray-800"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <MonitorIcon size={18} />
                      <div>
                        <div className="text-sm font-semibold">
                          {m.name || `Display ${m.id}`} {m.is_primary ? "(Primary)" : ""}
                        </div>
                        <div className="text-xs opacity-75">
                          {m.width}x{m.height} at ({m.x},{m.y})
                        </div>
                      </div>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-mono ${
                        isSelected
                          ? "bg-violet-700 text-white"
                          : "bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300"
                      }`}
                    >
                      {mQueue.length}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Slideshow Daemon Settings */}
          <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900">
            <h2 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-3 flex items-center gap-2">
              <Settings2 size={16} /> Rotation Settings
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Interval: {intervalSeconds}s
                </label>
                <input
                  type="range"
                  min="10"
                  max="3600"
                  step="10"
                  value={intervalSeconds}
                  onChange={(e) => setIntervalSeconds(parseInt(e.target.value, 10))}
                  className="w-full accent-violet-600"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Wallpaper Style
                </label>
                <select
                  value={style}
                  onChange={(e) =>
                    setStyle(
                      e.target.value as "fill" | "fit" | "stretch" | "center" | "tile" | "span"
                    )
                  }
                  className="w-full rounded-lg border border-gray-300 p-2 text-sm dark:border-gray-700 dark:bg-gray-800"
                >
                  <option value="fill">Fill (Crop to Display)</option>
                  <option value="fit">Fit (Keep Proportions)</option>
                  <option value="stretch">Stretch</option>
                  <option value="center">Centered</option>
                  <option value="tile">Tiled</option>
                  <option value="span">Span</option>
                </select>
              </div>

              <button
                type="button"
                data-testid="toggle-slideshow-button"
                onClick={() => void handleToggleDaemon()}
                disabled={loading}
                className={`flex w-full items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-bold text-white shadow transition-all ${
                  isRunning
                    ? "bg-red-600 hover:bg-red-700 shadow-red-500/20"
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

        {/* Right Column: Monitor Queue */}
        <div className="flex-1 flex flex-col rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-gray-900">
          <div className="flex items-center justify-between border-b pb-4 mb-4 dark:border-gray-800">
            <div>
              <h2 className="text-base font-bold">
                Monitor {selectedMonitor} Queue
              </h2>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {activeQueue.length} image(s) configured for this display
              </p>
            </div>
            {currentActivePath && (
              <div className="text-xs text-gray-500 flex items-center gap-1.5 truncate max-w-sm">
                <span className="font-semibold text-gray-700 dark:text-gray-300">Active:</span>
                <span className="truncate font-mono">{currentActivePath}</span>
              </div>
            )}
          </div>

          {/* Add Item Row */}
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              data-testid="queue-path-input"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              placeholder="Absolute image file path (/path/to/wallpaper.png)..."
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-800 dark:text-white"
            />
            <button
              type="button"
              data-testid="queue-add-button"
              onClick={() => void handleAddItem()}
              disabled={!newPath.trim() || loading}
              className="flex items-center gap-1.5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-violet-700 disabled:opacity-50"
            >
              <Plus size={16} /> Add to Queue
            </button>
          </div>

          {/* Queue List */}
          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {activeQueue.length === 0 ? (
              <div
                data-testid="empty-queue-notice"
                className="flex flex-col items-center justify-center p-12 text-center text-gray-400"
              >
                <ImageIcon size={40} className="mb-2 opacity-50" />
                <p className="text-sm font-medium">No images in queue for this monitor.</p>
                <p className="text-xs mt-1">Add file paths above to build the rotation playlist.</p>
              </div>
            ) : (
              activeQueue.map((itemPath, idx) => {
                const isActive = currentActivePath === itemPath;
                const fileName = itemPath.split(/[\\/]/).pop() || itemPath;

                return (
                  <div
                    key={`${itemPath}-${idx}`}
                    data-testid={`queue-item-${idx}`}
                    className={`flex items-center justify-between rounded-lg border p-3 text-sm transition-all ${
                      isActive
                        ? "border-emerald-500/60 bg-emerald-50/50 dark:border-emerald-700/60 dark:bg-emerald-950/20"
                        : "border-gray-200 bg-gray-50/60 dark:border-gray-800 dark:bg-gray-800/40"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="flex h-6 w-6 items-center justify-center rounded bg-gray-200 dark:bg-gray-700 text-xs font-mono font-bold">
                        {idx + 1}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold truncate">{fileName}</span>
                          {isActive && (
                            <span className="flex items-center gap-1 rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300">
                              <CheckCircle2 size={10} /> Active
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-gray-400 font-mono truncate">{itemPath}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        data-testid={`set-active-${idx}`}
                        onClick={() => void handleSetActiveWallpaper(itemPath)}
                        disabled={loading}
                        className="rounded p-1.5 text-xs font-medium text-emerald-600 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-950/50"
                        title="Set immediately as active desktop wallpaper"
                      >
                        Set Active
                      </button>
                      <button
                        type="button"
                        data-testid={`move-up-${idx}`}
                        onClick={() => void handleMoveItem(idx, "up")}
                        disabled={idx === 0 || loading}
                        className="rounded p-1.5 text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-30"
                        title="Move Up"
                      >
                        <ArrowUp size={14} />
                      </button>
                      <button
                        type="button"
                        data-testid={`move-down-${idx}`}
                        onClick={() => void handleMoveItem(idx, "down")}
                        disabled={idx === activeQueue.length - 1 || loading}
                        className="rounded p-1.5 text-gray-500 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-30"
                        title="Move Down"
                      >
                        <ArrowDown size={14} />
                      </button>
                      <button
                        type="button"
                        data-testid={`remove-item-${idx}`}
                        onClick={() => void handleRemoveItem(idx)}
                        disabled={loading}
                        className="rounded p-1.5 text-red-500 hover:bg-red-50 dark:hover:bg-red-950/50"
                        title="Remove from queue"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Status Message Footer */}
          {statusMessage && (
            <div
              data-testid="status-message"
              className={`mt-4 rounded-lg p-2.5 text-xs font-medium ${
                statusType === "error"
                  ? "bg-red-100 text-red-800 dark:bg-red-950/50 dark:text-red-300 border border-red-200 dark:border-red-800"
                  : statusType === "success"
                  ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800"
                  : "bg-blue-100 text-blue-800 dark:bg-blue-950/50 dark:text-blue-300"
              }`}
            >
              {statusMessage}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
