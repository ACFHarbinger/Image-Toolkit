import React from "react";

// --- QueueItemWidget ---
interface QueueItemWidgetProps {
  path: string;
  pixmapSrc: string; // In web, we pass the image source URL/Path
}

export const QueueItemWidget: React.FC<QueueItemWidgetProps> = ({
  path,
  pixmapSrc,
}) => {
  // Extract filename from path (mocking Python's Path(path).name)
  const filename = path.split(/[/\\]/).pop() || path;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        width: "350px",
        height: "70px",
        padding: "5px",
        boxSizing: "border-box",
      }}
    >
      {/* Image Preview */}
      <img
        src={pixmapSrc}
        alt="preview"
        style={{
          width: "80px",
          height: "60px",
          objectFit: "contain",
          borderRadius: "4px",
          border: "1px solid #4f545c",
          marginRight: "10px",
          flexShrink: 0,
        }}
      />

      {/* Filename Label */}
      <div
        title={path}
        style={{
          color: "#b9bbbe",
          fontSize: "12px",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "normal", // Word wrap
          lineHeight: "1.2",
        }}
      >
        {filename}
      </div>
    </div>
  );
};
