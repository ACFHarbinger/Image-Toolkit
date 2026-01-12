import React, { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { MonitorDropWidget } from "./MonitorDropWidget";

interface MonitorInfo {
  name: string;
  width: number;
  height: number;
  x: number;
  y: number;
}

interface MonitorLayoutProps {
  onMonitorImagesChange: (pathMap: Record<string, string>) => void;
}

export const MonitorLayout: React.FC<MonitorLayoutProps> = ({
  onMonitorImagesChange,
}) => {
  const [monitors, setMonitors] = useState<MonitorInfo[]>([]);
  const [pathMap, setPathMap] = useState<Record<string, string>>({});

  useEffect(() => {
    const fetchMonitors = async () => {
      try {
        const result: MonitorInfo[] = await invoke("get_monitors");
        setMonitors(result);
      } catch (err) {
        console.error("Failed to fetch monitors:", err);
      }
    };
    fetchMonitors();
  }, []);

  const handleImageDropped = (monitorId: string, filePath: string) => {
    const newPathMap = { ...pathMap, [monitorId]: filePath };
    setPathMap(newPathMap);
    onMonitorImagesChange(newPathMap);
  };

  const handleClear = (monitorId: string) => {
    const newPathMap = { ...pathMap };
    delete newPathMap[monitorId];
    setPathMap(newPathMap);
    onMonitorImagesChange(newPathMap);
  };

  return (
    <div className="flex flex-wrap gap-6 justify-center p-6 bg-gray-100 dark:bg-gray-900/30 rounded-xl border border-gray-200 dark:border-gray-800">
      {monitors.map((m, idx) => (
        <div key={idx} className="flex flex-col items-center">
          <MonitorDropWidget
            monitor={{ id: idx.toString(), name: m.name }}
            monitorId={idx.toString()}
            onImageDropped={handleImageDropped}
            onDoubleClicked={() => {}}
            onClearRequested={handleClear}
          />
          <div className="mt-2 text-xs text-gray-500 font-mono">
            {m.width}x{m.height} @ ({m.x}, {m.y})
          </div>
        </div>
      ))}
      {monitors.length === 0 && (
        <div className="py-12 text-gray-500 italic flex flex-col items-center">
          <div className="animate-pulse mb-2">Searching for monitors...</div>
          <p className="text-sm">
            Ensure the application has proper permissions.
          </p>
        </div>
      )}
    </div>
  );
};
