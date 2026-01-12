import React, { useState, useRef } from "react";
import { Monitor } from "lucide-react"; // Used as fallback icon, optional

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

  const hasValidImage = (items: DataTransferItemList | FileList): boolean => {
    // In a browser/electron drag, we check files
    if (items instanceof DataTransferItemList) {
      // During DragOver, we can only check 'kind', not the file extension securely
      // But we accept 'file'
      return Array.from(items).some((item) => item.kind === "file");
    }
    return Array.from(items).some((file) =>
      SUPPORTED_IMG_FORMATS.some((ext) =>
        file.name.toLowerCase().endsWith(ext),
      ),
    );
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (hasValidImage(e.dataTransfer.items)) {
      setIsDragging(true);
    }
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

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      const isSupported = SUPPORTED_IMG_FORMATS.some((ext) =>
        file.name.toLowerCase().endsWith(ext),
      );

      if (isSupported) {
        // In Electron, 'file.path' gives the full OS path.
        // In pure web, this is restricted. Assuming Electron context here.
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
  React.useEffect(() => {
    const handleClick = () => setContextMenuPos(null);
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, []);

  const monitorName = monitor.name
    ? `Monitor ${monitorId} (${monitor.name})`
    : `Monitor ${monitorId}`;

  return (
    <>
      <div
        onDragEnter={handleDragEnter}
        onDragOver={(e) => e.preventDefault()} // Necessary to allow dropping
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onDoubleClick={() => onDoubleClicked(monitorId)}
        onContextMenu={handleContextMenu}
        style={{
          width: "220px",
          height: "160px",
          backgroundColor: isDragging ? "#40444b" : "#36393f",
          border: isDragging ? "2px solid #5865f2" : "2px dashed #4f545c",
          borderRadius: "8px",
          color: "#b9bbbe",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "10px",
          textAlign: "center",
          position: "relative",
          transition: "all 0.2s",
          cursor: "default",
          overflow: "hidden", // Clip image
        }}
      >
        {imagePath ? (
          <img
            src={imagePath}
            alt="Monitor Background"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        ) : (
          <>
            <b style={{ marginBottom: "10px" }}>{monitorName}</b>
            <span style={{ fontSize: "14px" }}>Drag and Drop Image Here</span>
          </>
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
