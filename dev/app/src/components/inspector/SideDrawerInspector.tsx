import React, { useState } from "react";
import { CameraBookmark, WorldStateData } from "../../types";

interface SideDrawerInspectorProps {
  isOpen: boolean;
  selectedEntity: any;
  worldState: WorldStateData | null;
  onClose: () => void;
  onSaveBookmark: (label: string) => void;
  onSelectBookmark: (bm: CameraBookmark) => void;
}

export const SideDrawerInspector: React.FC<SideDrawerInspectorProps> = ({
  isOpen,
  selectedEntity,
  worldState,
  onClose,
  onSaveBookmark,
  onSelectBookmark,
}) => {
  const [noteText, setNoteText] = useState("");

  if (!isOpen) return null;

  const handleSave = () => {
    onSaveBookmark(noteText);
    setNoteText("");
  };

  return (
    <aside className="side-drawer">
      <div className="drawer-header">
        <h2>Inspector</h2>
        <button onClick={onClose} title="Close Inspector">
          &times;
        </button>
      </div>

      <div className="drawer-content">
        <div className="inspector-section">
          <h4>Selected Entity</h4>
          <table className="info-table">
            <tbody>
              <tr>
                <td className="label">ID:</td>
                <td className="val">
                  {selectedEntity?.id || selectedEntity?.name || "--"}
                </td>
              </tr>
              <tr>
                <td className="label">Layer:</td>
                <td className="val">{selectedEntity?.layer || "--"}</td>
              </tr>
              <tr>
                <td className="label">Subsystem:</td>
                <td className="val">
                  {selectedEntity?.cluster_id || selectedEntity?.kind || "--"}
                </td>
              </tr>
              <tr>
                <td className="label">Latency:</td>
                <td className="val">
                  {selectedEntity?.latency_ms
                    ? `${selectedEntity.latency_ms.toFixed(1)} ms`
                    : "--"}
                </td>
              </tr>
              <tr>
                <td className="label">Calls / Volume:</td>
                <td className="val">
                  {selectedEntity?.call_count
                    ? `${selectedEntity.call_count} ops`
                    : "--"}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="inspector-section">
          <h4>Investigation Note (@ Mention)</h4>
          <textarea
            className="annotation-box"
            placeholder="Write observation, tag @module or @bug..."
            value={noteText}
            onChange={(e) => setNoteText(e.target.value)}
          />
          <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
            <button
              onClick={handleSave}
              className="primary"
              style={{ flex: 1 }}
            >
              Save Camera Bookmark
            </button>
          </div>
        </div>

        <div className="inspector-section">
          <h4>Investigation Bookmarks</h4>
          <div className="bookmark-list">
            {worldState?.bookmarks?.map((bm) => (
              <div
                key={bm.id}
                className="bookmark-pill"
                onClick={() => onSelectBookmark(bm)}
              >
                <span>📌 {bm.label}</span>
                <span style={{ color: "#64748b" }}>
                  {bm.pinned_node_id || "Vantage"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
};
