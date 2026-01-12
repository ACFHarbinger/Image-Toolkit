import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { MonitorLayout } from "../../components/MonitorLayout";
import {
  Play,
  Square,
  Settings2,
  Clock,
  Monitor as MonitorIcon,
  Info,
} from "lucide-react";

const WallpaperTab: React.FC = () => {
  const [monitorPaths, setMonitorPaths] = useState<Record<string, string>>({});
  const [style, setStyle] = useState("Fill");
  const [interval, setIntervalValue] = useState(300);
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState("");
  const [countdown, setCountdown] = useState<number | null>(null);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isRunning && countdown !== null) {
      if (countdown > 0) {
        timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      } else {
        setCountdown(interval);
      }
    }
    return () => clearTimeout(timer);
  }, [isRunning, countdown, interval]);

  const handleMonitorImagesChange = (pathMap: Record<string, string>) => {
    setMonitorPaths(pathMap);
  };

  const handleSetWallpaper = async () => {
    if (Object.keys(monitorPaths).length === 0) {
      setStatus("Error: No images assigned to monitors");
      return;
    }
    try {
      setStatus("Setting wallpaper...");
      await invoke("set_wallpaper", {
        pathMap: monitorPaths,
        monitors: Object.keys(monitorPaths).map((k) => parseInt(k)),
        style,
      });
      setStatus("Wallpaper set successfully!");
    } catch (err) {
      console.error(err);
      setStatus(`Error: ${err}`);
    }
  };

  const handleToggleSlideshow = async () => {
    try {
      const nextState = !isRunning;

      if (nextState && Object.keys(monitorPaths).length === 0) {
        setStatus("Error: Assign images to monitors first");
        return;
      }

      // Update config first
      const config = {
        running: nextState,
        interval_seconds: interval,
        style,
        monitor_queues: Object.entries(monitorPaths).reduce(
          (acc, [id, path]) => {
            acc[id] = [path]; // For now, single item queue for this prototype
            return acc;
          },
          {} as Record<string, string[]>,
        ),
        current_paths: monitorPaths,
        monitor_geometries: {}, // Could be populated if we want precise layout
      };

      await invoke("update_slideshow_config", { config });
      await invoke("toggle_slideshow_daemon", { running: nextState });

      setIsRunning(nextState);
      setCountdown(nextState ? interval : null);
      setStatus(
        nextState
          ? "Slideshow started (Background Daemon)"
          : "Slideshow stopped",
      );
    } catch (err) {
      console.error(err);
      setStatus(`Error: ${err}`);
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50 dark:bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b dark:border-gray-800 bg-white dark:bg-gray-800/50 flex justify-between items-center">
        <h2 className="text-lg font-bold flex items-center gap-2">
          <MonitorIcon className="text-violet-500" /> Multi-Monitor Wallpaper
          Manager
        </h2>
        {isRunning && countdown !== null && (
          <div className="flex items-center gap-2 px-3 py-1 bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 rounded-full text-sm font-mono animate-pulse">
            <Clock size={14} /> Next update in: {Math.floor(countdown / 60)}m{" "}
            {countdown % 60}s
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* Monitor Layout Area */}
        <section>
          <div className="flex items-center gap-2 mb-4 text-sm font-semibold text-gray-500 uppercase tracking-wider">
            Monitor Discovery & Assignment
          </div>
          <MonitorLayout onMonitorImagesChange={handleMonitorImagesChange} />
          <div className="mt-2 flex items-start gap-2 text-xs text-gray-400">
            <Info size={14} className="mt-0.5 flex-shrink-0" />
            <p>
              Drag and drop images onto monitor blocks above. Double-click to
              preview. Right-click to clear.
            </p>
          </div>
        </section>

        {/* Controls Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Wallpaper Settings */}
          <div className="bg-white dark:bg-gray-800 p-5 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
              <Settings2 size={16} className="text-gray-400" /> General Settings
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase">
                  Scaling Style
                </label>
                <select
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-700 dark:text-white p-2 text-sm focus:ring-2 focus:ring-violet-500 outline-none"
                >
                  <option value="Fill">Fill (Zoom)</option>
                  <option value="Fit">Fit (Letterbox)</option>
                  <option value="Stretch">Stretch</option>
                  <option value="Tile">Tile</option>
                  <option value="Center">Center</option>
                  <option value="Span">Span (Across Monitors)</option>
                </select>
              </div>

              <button
                onClick={handleSetWallpaper}
                disabled={Object.keys(monitorPaths).length === 0}
                className={`w-full py-2.5 rounded-lg font-bold text-white transition shadow-lg
                  ${
                    Object.keys(monitorPaths).length > 0
                      ? "bg-gradient-to-r from-emerald-500 to-teal-600 hover:shadow-emerald-500/20"
                      : "bg-gray-400 cursor-not-allowed"
                  }`}
              >
                Apply Static Wallpaper
              </button>
            </div>
          </div>

          {/* Slideshow Settings */}
          <div className="bg-white dark:bg-gray-800 p-5 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
            <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
              <Play size={16} className="text-gray-400" /> Slideshow (Daemon)
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1.5 uppercase">
                  Update Interval (Seconds)
                </label>
                <div className="flex items-center gap-3">
                  <input
                    type="range"
                    min="10"
                    max="3600"
                    step="10"
                    value={interval}
                    onChange={(e) => setIntervalValue(parseInt(e.target.value))}
                    className="flex-1 accent-violet-500"
                  />
                  <span className="text-sm font-mono w-16 text-right">
                    {interval}s
                  </span>
                </div>
              </div>

              <button
                onClick={handleToggleSlideshow}
                className={`w-full py-2.5 rounded-lg font-bold text-white transition flex items-center justify-center gap-2 shadow-lg
                  ${
                    isRunning
                      ? "bg-red-500 hover:bg-red-600 shadow-red-500/20"
                      : "bg-violet-500 hover:bg-violet-600 shadow-violet-500/20"
                  }`}
              >
                {isRunning ? (
                  <>
                    <Square size={18} fill="currentColor" /> Stop Slideshow
                  </>
                ) : (
                  <>
                    <Play size={18} fill="currentColor" /> Start Slideshow
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Status Message */}
        {status && (
          <div
            className={`p-3 rounded-lg text-sm font-medium animate-in fade-in slide-in-from-bottom-2 duration-300 ${
              status.startsWith("Error")
                ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
                : "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800"
            }`}
          >
            {status}
          </div>
        )}
      </div>
    </div>
  );
};

export default WallpaperTab;
