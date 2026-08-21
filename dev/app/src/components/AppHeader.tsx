import React from "react";
import { WorkspaceInfo } from "../types";

interface AppHeaderProps {
  workspace: WorkspaceInfo;
  activeView: string;
  sidecarStatus: string;
  isDrawerOpen: boolean;
  onViewChange: (view: string) => void;
  onToggleDrawer: () => void;
  onSwitchWorkspace: () => void;
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  workspace,
  activeView,
  sidecarStatus,
  isDrawerOpen,
  onViewChange,
  onToggleDrawer,
  onSwitchWorkspace,
}) => {
  return (
    <header className="app-header">
      <div className="header-left">
        <span className="brand-title">DevTool v2</span>
        <span className="workspace-badge">
          {workspace.name} — {workspace.root}
        </span>
        <div className="view-tabs">
          <button
            className={`tab-btn ${activeView === "view-galaxy" ? "active" : ""}`}
            onClick={() => onViewChange("view-galaxy")}
          >
            3D Galaxy
          </button>
          <button
            className={`tab-btn ${activeView === "view-flame" ? "active" : ""}`}
            onClick={() => onViewChange("view-flame")}
          >
            2D Flame Graph
          </button>
          <button
            className={`tab-btn ${activeView === "view-metrics" ? "active" : ""}`}
            onClick={() => onViewChange("view-metrics")}
          >
            Metrics Timeline
          </button>
          <button
            className={`tab-btn ${activeView === "view-scrubber" ? "active" : ""}`}
            onClick={() => onViewChange("view-scrubber")}
          >
            4D Pipeline Scrubber
          </button>
        </div>
      </div>

      <div className="header-right">
        <div className="sidecar-badge">{sidecarStatus}</div>
        <button
          onClick={onToggleDrawer}
          className={isDrawerOpen ? "active" : ""}
          title="Toggle Inspector"
        >
          Inspector
        </button>
        <button onClick={onSwitchWorkspace}>Switch workspace</button>
      </div>
    </header>
  );
};
