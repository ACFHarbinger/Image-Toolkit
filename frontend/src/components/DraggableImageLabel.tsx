import React from "react";

// --- DraggableImageLabel ---
interface DraggableProps extends LabelProps {
  size: number;
}

export const DraggableImageLabel: React.FC<DraggableProps> = ({
  path,
  src,
  size,
  onPathClicked,
  onPathDoubleClicked,
  onPathRightClicked,
}) => {
  const handleDragStart = (e: React.DragEvent) => {
    if (!src) {
      e.preventDefault();
      return;
    }
    // Set file path as URL list (standard for file drops)
    e.dataTransfer.setData("text/plain", path);
    // In Electron/Native contexts, we might use e.dataTransfer.files logic via IPC

    e.dataTransfer.effectAllowed = "move";

    // HTML5 Drag Image logic (simplified, usually browser handles ghost image)
    const img = new Image();
    img.src = src;
    e.dataTransfer.setDragImage(img, size / 2, size / 2);
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    onPathRightClicked?.(e, path);
  };

  return (
    <div
      data-selectable="true"
      data-path={path}
      draggable={!!src}
      onDragStart={handleDragStart}
      style={{
        ...getLabelStyle(false), // Default style
        width: `${size}px`,
        height: `${size}px`,
      }}
      onClick={() => onPathClicked?.(path)}
      onDoubleClick={() => onPathDoubleClicked?.(path)}
      onContextMenu={handleContextMenu}
    >
      {src ? (
        <img
          src={src}
          alt="thumbnail"
          draggable={false} // Prevent default img drag, use parent div
          style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
        />
      ) : (
        <span>Loading...</span>
      )}
    </div>
  );
};
