import React, { useState, useEffect } from "react";
import { Monitor } from "lucide-react";
import { convertFileSrc } from "@tauri-apps/api/core";

interface MonitorData {
  id: string;
  name: string;
  // other properties from screeninfo...
}

interface MonitorDropWidgetProps {
  monitor: MonitorData;
  monitorId: string;
  // Signals -> Props
  onImageDropped: (monitorId: string, filePath: string) => void;
  onDoubleClicked: (monitorId: string) => void;
  onClearRequested: (monitorId: string) => void;
}

const SUPPORTED_IMG_FORMATS = [".png", ".jpg", ".jpeg", ".bmp", ".gif"];

export const MonitorDropWidget: React.FC<MonitorDropWidgetProps> = ({
  monitor,
  monitorId,
  onImageDropped,
  onDoubleClicked,
  onClearRequested,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [imagePath, setImagePath] = useState<string | null>(null);
  const [contextMenuPos, setContextMenuPos] = useState<{
    x: number;
    y: number;
  } | null>(null);

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    // 1. Check for internal path (text/plain) from DraggableImageLabel
    const internalPath = e.dataTransfer.getData("text/plain");
    if (internalPath) {
      setImagePath(internalPath);
      onImageDropped(monitorId, internalPath);
      return;
    }

    // 2. Check for external files
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      const isSupported = SUPPORTED_IMG_FORMATS.some((ext) =>
        file.name.toLowerCase().endsWith(ext),
      );

      if (isSupported) {
        const filePath = (file as any).path || URL.createObjectURL(file);
        setImagePath(filePath);
        onImageDropped(monitorId, filePath);
      }
    }
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    setContextMenuPos({ x: e.clientX, y: e.clientY });
  };

  // Close context menu on click elsewhere
  useEffect(() => {
    const handleClick = () => setContextMenuPos(null);
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  const monitorName = monitor.name
    ? `${monitor.name}`
    : `Monitor ${monitorId}`;

  return (
    <>
      <div
        onDragEnter={handleDragEnter}
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        }}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onDoubleClick={() => onDoubleClicked(monitorId)}
        onContextMenu={handleContextMenu}
        className={`relative w-[280px] h-[180px] rounded-xl border-2 transition-all duration-300 flex flex-col items-center justify-center overflow-hidden group cursor-pointer
            ${isDragging
            ? "bg-violet-500/10 border-violet-500 shadow-[0_0_20px_rgba(139,92,246,0.3)] scale-[1.02]"
            : "bg-gray-50 dark:bg-gray-800/50 border-gray-200 dark:border-gray-700 border-dashed hover:border-violet-400 dark:hover:border-violet-600 hover:bg-gray-100 dark:hover:bg-gray-800"
          }`}
      >
        {imagePath ? (
          <>
            <img
              src={imagePath.startsWith("blob:") ? imagePath : convertFileSrc(imagePath)}
              alt="Monitor Background"
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
              <span className="text-white text-xs font-bold drop-shadow-md px-3 py-1 bg-black/20 rounded-full backdrop-blur-sm">
                {monitorName}
              </span>
              <span className="text-white/70 text-[10px]">Double-click to preview</span>
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center gap-3 text-gray-400 dark:text-gray-500">
            <Monitor size={48} strokeWidth={1.5} className={isDragging ? "text-violet-500 animate-bounce" : ""} />
            <div className="flex flex-col items-center">
              <b className="text-sm dark:text-gray-300">{monitorName}</b>
              <span className="text-xs">Drop image here</span>
            </div>
          </div>
        )}
      </div>

      {/* Custom Context Menu Simulation */}
      {contextMenuPos && (
        <div
          style={{
            position: "fixed",
            top: contextMenuPos.y,
            left: contextMenuPos.x,
            backgroundColor: "#18191c",
            border: "1px solid #2f3136",
            borderRadius: "4px",
            padding: "5px 0",
            zIndex: 1000,
            boxShadow: "0 2px 5px rgba(0,0,0,0.5)",
          }}
        >
          <div
            onClick={() => {
              onClearRequested(monitorId);
              setImagePath(null);
            }}
            style={{
              padding: "8px 12px",
              cursor: "pointer",
              color: "#dcddde",
              fontSize: "14px",
            }}
            onMouseEnter={(e) =>
              (e.currentTarget.style.backgroundColor = "#4752c4")
            }
            onMouseLeave={(e) =>
              (e.currentTarget.style.backgroundColor = "transparent")
            }
          >
            Clear All Images (Current and Queue)
          </div>
        </div>
      )}
    </>
  );
};
